"""Reproducible adversarial API requests that never execute frontend validation."""

import json
import random
from copy import deepcopy

from test_accounts import account_database as account_database
from test_document_package import walk
from test_document_persistence import DATA
from test_document_persistence import document_store as document_store
from test_document_saves import save, start
from test_template_copies import amounts

from app.documents.package import DocxPackage


def typed_payload(payload, kind, value):
    result = deepcopy(payload)
    result["document"] = DocxPackage(DATA).model
    fields = [node for node in walk(result["document"]) if node["type"] == "field"]
    result["document"]["attrs"] = {
        "review": {
            "sourceVersion": None,
            "items": [
                dict(
                    id="candidate:" + field["attrs"]["id"],
                    occurrenceId=field["attrs"]["id"],
                    reason="native_control",
                    sourceKey=None,
                    context="",
                    label=field["attrs"]["label"],
                    key=field["attrs"]["key"],
                    type="text",
                    decision="accepted",
                    missing=False,
                    location={"kind": "control", "id": field["attrs"]["id"]},
                )
                for field in fields
            ],
        }
    }
    node = fields[0]
    node["content"] = [{"type": "text", "text": value}] if value else []
    entry = next(
        entry
        for entry in result["document"]["attrs"]["review"]["items"]
        if entry["location"] == {"kind": "control", "id": node["attrs"]["id"]}
    )
    entry["type"] = kind
    return result


def test_api_rejects_typed_value_and_length_bypasses_without_writing():
    owner, web, saved, payload = start()
    before = amounts(owner)
    failures = []
    for index, (kind, value) in enumerate(
        [
            ("number", "NaN"),
            ("number", "Infinity"),
            ("number", "1e3"),
            ("number", "12 34"),
            ("number", "1,2.3"),
            ("number", "１２"),
            ("date", "31.02.2024"),
            ("date", "29.02.1900"),
            ("date", "0000-01-01"),
            ("date", "2024-13-01"),
            ("text", "x" * 65537),
            ("text", "\x00"),
        ]
    ):
        response = save(web, saved, typed_payload(payload, kind, value), f"bad-{index}")
        if response.status_code != 422:
            failures.append((index, kind, response.status_code))
            # Stop after an accepted save: its revision would mask later probes.
            break
        assert amounts(owner) == before
    assert not failures, failures
    assert web.get(f"/api/documents/{saved['id']}").json() == saved


def test_seeded_malformed_save_nodes_fail_closed():
    owner, web, saved, payload = start()
    before = amounts(owner)
    rng = random.Random(942)
    mutations = [None, True, 0, 1.5, "private-value", [], {}, [None], {"type": []}]
    cases = []
    for key in ("type", "content", "attrs"):
        for value in mutations:
            candidate = deepcopy(payload)
            candidate["document"][key] = value
            cases.append(candidate)
    rng.shuffle(cases)
    for index, candidate in enumerate(cases):
        # Empty attrs is a supported legacy review-free document.
        if candidate["document"].get("attrs") == {}:
            continue
        response = save(web, saved, candidate, f"node-{index}")
        assert response.status_code == 422, (index, response.status_code, response.text)
        assert "private-value" not in response.text
        assert amounts(owner) == before


def test_profile_and_copy_unicode_bypasses_are_client_errors():
    owner, web, saved, _ = start()
    before = amounts(owner)
    for value in ("a\x00b", "\ud800"):
        response = web.patch(
            "/api/profile",
            content=json.dumps({"display_name": value}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422, response.text
    response = web.post(
        f"/api/documents/{saved['id']}/copies",
        content=json.dumps(
            {"source_version_id": saved["current_version_id"], "title": "\ud800"}
        ),
        headers={"Content-Type": "application/json", "Idempotency-Key": "unicode"},
    )
    assert response.status_code == 422, response.text
    assert amounts(owner) == before


def test_typed_probe_positive_control():
    _, web, saved, payload = start()
    response = save(web, saved, typed_payload(payload, "number", "-1 234,50"))
    assert response.status_code == 201, response.text


def test_authentication_unicode_and_request_shape_boundaries():
    from test_accounts import PASSWORD, browser

    owner, web, _, _ = start()
    cases = [
        (
            "PATCH",
            "/api/profile",
            "display_name",
            [None, True, 0, [], {}, "", " ", "x" * 121],
        ),
        (
            "PATCH",
            "/api/profile/language",
            "ui_language",
            [None, True, 1, [], {}, "", "ua", "EN"],
        ),
        (
            "POST",
            "/api/profile/password",
            "new_password",
            [None, True, 1, [], {}, "", "x" * 9, "x" * 1025, "\ud800" * 10],
        ),
    ]
    for method, path, field, values in cases:
        for value in values:
            body = {field: value}
            if field == "new_password":
                body["current_password"] = PASSWORD
            response = web.request(
                method,
                path,
                content=json.dumps(body),
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 422, (path, response.text)
    anonymous = browser()
    for field, values in (
        ("login", [None, True, [], {}, "", "x" * 255, "a\x00b", "\ud800"]),
        ("password", [None, True, [], {}, "", "x" * 1025, "\ud800"]),
    ):
        for value in values:
            body = {"login": owner.login, "password": PASSWORD, field: value}
            response = anonymous.post(
                "/api/auth/login",
                content=json.dumps(body),
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 422, (field, response.text)


def test_seeded_nested_node_type_mutations():
    owner, web, saved, payload = start()
    before = amounts(owner)
    rng = random.Random(942)
    node_count = len(list(walk(payload["document"])))
    for index in range(128):
        candidate = deepcopy(payload)
        node = list(walk(candidate["document"]))[rng.randrange(node_count)]
        node["type"] = rng.choice([None, True, 3, [], {}, "unknown-node"])
        response = save(web, saved, candidate, f"nested-{index}")
        assert response.status_code == 422, (index, response.status_code)
        assert amounts(owner) == before
