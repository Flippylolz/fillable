from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, update
from test_accounts import PASSWORD, account, browser
from test_accounts import account_database as account_database
from test_document_package import walk
from test_document_persistence import DATA, client, upload
from test_document_persistence import document_store as document_store
from test_editing_leases import request as lease_request
from test_template_copies import amounts, copy, revision
from test_working_review import FIXTURE

from app.accounts import service as accounts_service
from app.accounts.schema import AccountInput, sessions, users
from app.documents import routes
from app.documents.lease_schema import leases
from app.documents.package import DocxPackage
from app.documents.schema import resources, versions
from app.fields.validation import validate_snapshot
from app.fields.working import validate_working
from app.infrastructure import database
from app.jobs import worker
from app.jobs.schema import jobs
from app.storage.configuration import configured
from app.storage.quotas import set_override
from app.storage.service import Storage, now


def start(kind="template"):
    owner = account()
    web = client()
    saved = upload(web, kind=kind).json()
    tab = uuid4()
    lease = lease_request(web, saved, tab).json()
    model = deepcopy(FIXTURE)
    model["attrs"]["review"]["sourceVersion"] = saved["current_version_id"]
    payload = dict(
        source_version_id=saved["current_version_id"],
        client_id=str(tab),
        lease_id=lease["lease_id"],
        document=model,
    )
    return owner, web, saved, payload


def save(web, saved, payload, key="save"):
    return web.post(
        f"/api/documents/{saved['id']}/versions",
        json=payload,
        headers={"Idempotency-Key": key},
    )


@pytest.mark.parametrize("kind", ["template", "document"])
def test_atomic_save_reopen_worker_lease_successor_and_exact_late_replay(kind):
    owner, web, saved, payload = start(kind)
    response = save(web, saved, payload)
    assert response.status_code == 201, response.text
    first = response.json()
    current = first["resource"]
    assert first["saved_version_id"] == current["current_version_id"]
    assert (
        first["saved_number"] == 2 and response.headers["cache-control"] == "no-store"
    )
    endpoint = f"/api/documents/{saved['id']}"
    model = web.get(endpoint + "/content").json()["document"]
    assert model == payload["document"]
    data = web.get(endpoint + "/download").content
    assert first["saved_size_bytes"] == len(data)
    assert first["saved_digest"] == DocxPackage(data).digest
    assert amounts(owner) == (len(DATA) + len(data), 0)
    with database().connect() as connection:
        row = (
            connection.execute(
                select(versions).where(versions.c.id == UUID(first["saved_version_id"]))
            )
            .mappings()
            .one()
        )
        assert "attrs" not in row["document_model"]
        assert row["field_review"] == model["attrs"]["review"]
        original = connection.execute(select(resources.c.original_file_id)).scalar_one()
        job = (
            connection.execute(
                select(jobs).where(jobs.c.source_version_id == row["id"])
            )
            .mappings()
            .one()
        )
    with configured().read(owner.id, original) as stream:
        assert stream.read() == DATA
    worker.process(str(job["id"]), 1)
    detected = web.get(endpoint + "/fields").json()
    assert detected["status"] == "succeeded"
    validate_snapshot(detected["snapshot"], row["id"], row["document_model"])
    # A delayed cleanup for the old revision must not delete its updated lease.
    assert (
        lease_request(
            web, saved, UUID(payload["client_id"]), "release", payload["lease_id"]
        ).status_code
        == 200
    )
    renewed = lease_request(
        web, current, UUID(payload["client_id"]), "renew", payload["lease_id"]
    )
    assert renewed.status_code == 200
    changed = deepcopy(payload)
    changed["source_version_id"] = current["current_version_id"]
    field = next(node for node in walk(changed["document"]) if node["type"] == "field")
    for text in field["content"]:
        text["text"] = "Ї" * (len(text["text"].encode("utf-16-le")) // 2)
    second_response = save(web, current, changed, "second")
    assert second_response.status_code == 201, second_response.text
    second = second_response.json()
    assert second["saved_number"] == 3
    second_bytes = web.get(endpoint + "/download").content
    assert second_bytes != data
    before = amounts(owner)
    replay = save(web, saved, payload).json()
    assert replay["saved_version_id"] == first["saved_version_id"]
    assert replay["saved_digest"] == first["saved_digest"]
    assert replay["resource"]["current_version_id"] == second["saved_version_id"]
    assert amounts(owner) == before == (len(DATA) + len(data) + len(second_bytes), 0)
    assert web.get(endpoint + "/content").json()["document"] == changed["document"]
    if kind == "template":
        copied = copy(web, second["resource"]).json()
        copied_url = f"/api/documents/{copied['id']}"
        validate_working(
            web.get(copied_url + "/content").json()["document"],
            UUID(copied["current_version_id"]),
        )
        assert web.get(copied_url + "/download").content == second_bytes
        assert web.delete(endpoint).status_code == 200
        assert amounts(owner) == (len(second_bytes), 0)
        assert web.get(copied_url + "/download").content == second_bytes
        with database().connect() as connection:
            assert all(
                value is None
                for value in connection.execute(
                    select(versions.c.field_review).where(
                        versions.c.document_id == UUID(saved["id"])
                    )
                ).scalars()
            )


def test_review_only_save_is_a_charged_revision_and_retry_never_double_charges():
    owner, web, saved, payload = start()
    first = save(web, saved, payload).json()
    before = amounts(owner)
    changed = deepcopy(payload)
    changed["source_version_id"] = first["saved_version_id"]
    item = next(
        item
        for item in changed["document"]["attrs"]["review"]["items"]
        if item["decision"] == "proposed"
    )
    item["decision"] = "dismissed"
    second = save(web, first["resource"], changed, "review").json()
    assert second["saved_digest"] == first["saved_digest"]
    assert second["saved_version_id"] != first["saved_version_id"]
    assert amounts(owner) == (before[0] + first["saved_size_bytes"], 0)
    assert save(web, first["resource"], changed, "review").json() == second
    assert save(web, first["resource"], payload, "review").status_code == 409


@pytest.mark.parametrize(
    "change",
    [
        "revision",
        "client",
        "generation",
        "expired",
        "session",
        "owner",
        "csrf",
        "anonymous",
    ],
)
def test_unowned_or_stale_saves_leave_current_bytes_and_usage(change):
    owner, web, saved, payload = start()
    before = amounts(owner)
    expected = 409
    if change == "revision":
        payload["source_version_id"] = str(uuid4())
    elif change == "client":
        payload["client_id"] = str(uuid4())
    elif change == "generation":
        payload["lease_id"] = str(uuid4())
    elif change == "expired":
        with database().begin() as connection:
            connection.execute(
                update(leases).values(expires_at=now() - timedelta(seconds=1))
            )
    elif change == "session":
        with database().begin() as connection:
            connection.execute(
                update(sessions).values(expires_at=now() - timedelta(seconds=1))
            )
        expected = 401
    elif change == "owner":
        peer = accounts_service.provision(
            AccountInput(email="peer@example.test", display_name="Peer"), PASSWORD
        )
        web = browser()
        login = web.post(
            "/api/auth/login", json={"email": peer.login, "password": PASSWORD}
        )
        web.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        expected = 404
    elif change == "csrf":
        web.headers["X-CSRF-Token"] = "bad"
        expected = 403
    else:
        web = browser()
        expected = 401
    assert save(web, saved, payload).status_code == expected
    assert amounts(owner) == before
    with database().connect() as connection:
        assert connection.execute(
            select(resources.c.current_version_id)
        ).scalar_one() == UUID(saved["current_version_id"])
        assert len(connection.execute(select(versions.c.id)).all()) == 1


@pytest.mark.parametrize(
    "race", ["lease", "quota", "revision", "deletion", "revocation"]
)
def test_finalization_rechecks_authority_and_policy_without_partial_commit(
    race, monkeypatch
):
    owner, web, saved, payload = start()
    original = Storage._finish
    entered = False

    def finish(store, *args):
        nonlocal entered
        if not entered:
            entered = True
            if race == "quota":
                set_override(owner.id, len(DATA))
            elif race == "revision":
                revision(owner, saved)
            elif race == "deletion":
                assert web.delete(f"/api/documents/{saved['id']}").status_code == 200
            else:
                with database().begin() as connection:
                    if race == "lease":
                        connection.execute(update(leases).values(lease_id=uuid4()))
                    else:
                        connection.execute(update(users).values(active=False))
        return original(store, *args)

    monkeypatch.setattr(Storage, "_finish", finish)
    response = save(web, saved, payload)
    assert response.status_code in (401, 404, 409), response.text
    assert amounts(owner)[1] == 0
    with database().connect() as connection:
        rows = connection.execute(select(versions)).mappings().all()
        assert len(rows) == (2 if race == "revision" else 1)
        assert all(row["field_review"] is None for row in rows)


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_saves_create_only_one_new_current_revision(same_key):
    owner, web, saved, payload = start()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda index: save(
                    web, saved, payload, "one" if same_key else str(index)
                ),
                range(2),
            )
        )
    assert all(response.status_code in (201, 409) for response in results)
    completed = next(
        response.json() for response in results if response.status_code == 201
    )
    assert amounts(owner) == (len(DATA) + completed["saved_size_bytes"], 0)
    with database().connect() as connection:
        assert len(connection.execute(select(versions.c.id)).all()) == 2


def test_save_body_admission_and_invalid_model_are_content_free(monkeypatch):
    owner, web, saved, payload = start()
    assert routes.UPLOAD_SLOTS.acquire(False) and routes.UPLOAD_SLOTS.acquire(False)
    try:
        assert save(web, saved, payload).status_code == 429
    finally:
        routes.UPLOAD_SLOTS.release()
        routes.UPLOAD_SLOTS.release()
    monkeypatch.setattr(routes, "SAVE_BODY_BYTES", 10)
    assert save(browser(), saved, payload).status_code == 401
    assert save(web, saved, payload).status_code == 413
    monkeypatch.setattr(routes, "SAVE_BODY_BYTES", 64 * 1024 * 1024)
    invalid = deepcopy(payload)
    invalid["document"]["attrs"]["review"]["sourceVersion"] = str(uuid4())
    assert save(web, saved, invalid, "invalid").status_code == 422
    invalid["document"] = {"type": "doc", "content": [{"private": "must not leak"}]}
    response = save(web, saved, invalid, "malformed")
    assert response.status_code == 422 and "private" not in response.text
    assert amounts(owner) == (len(DATA), 0)


def test_migration_preserves_embedded_review_and_refuses_destructive_downgrade():
    owner = account()
    web = client()
    saved = upload(web).json()
    revision(owner, saved, working=FIXTURE)
    with database().begin() as connection:
        connection.execute(
            update(versions)
            .where(versions.c.number == 2)
            .values(document_model=FIXTURE, field_review=None)
        )
    config = Config("alembic.ini")
    command.downgrade(config, "0008_editing_leases")
    command.upgrade(config, "head")
    with database().connect() as connection:
        row = (
            connection.execute(select(versions).where(versions.c.number == 2))
            .mappings()
            .one()
        )
        assert "attrs" not in row["document_model"]
        assert row["field_review"] == FIXTURE["attrs"]["review"]
    # Isolate 0009's review guard from the newer provenance migration guard.
    with database().begin() as connection:
        connection.execute(update(versions).values(parent_version_id=None))
    with pytest.raises(RuntimeError, match="refusing destructive downgrade"):
        command.downgrade(config, "0008_editing_leases")
    with database().begin() as connection:
        connection.execute(update(versions).values(field_review=None))
    command.downgrade(config, "0008_editing_leases")
    command.upgrade(config, "head")


def test_lost_commit_response_replays_committed_revision_without_exporting_again(
    monkeypatch,
):
    from sqlalchemy.exc import SQLAlchemyError

    from app.documents import saves

    owner, web, saved, payload = start()
    finish = Storage._finish

    def lose_response(store, *args):
        finish(store, *args)
        raise SQLAlchemyError("private response detail")

    monkeypatch.setattr(Storage, "_finish", lose_response)
    failed = save(web, saved, payload)
    assert failed.status_code == 503 and "private" not in failed.text
    before = amounts(owner)
    assert before[0] > len(DATA) and before[1] == 0
    monkeypatch.setattr(Storage, "_finish", finish)

    def forbidden_read(*args):
        raise AssertionError("A committed replay must not load a new source")

    monkeypatch.setattr(saves, "saved_row", forbidden_read)
    recovered = save(web, saved, payload)
    assert recovered.status_code == 201, recovered.text
    assert recovered.json()["saved_number"] == 2
    assert amounts(owner) == before


def test_disk_failure_preserves_previous_revision_and_allows_a_fresh_retry(monkeypatch):
    import errno

    owner, web, saved, payload = start()
    finish = Storage._finish

    def full_disk(*args):
        raise OSError(errno.ENOSPC, "private disk detail")

    monkeypatch.setattr(Storage, "_finish", full_disk)
    failed = save(web, saved, payload)
    assert failed.status_code == 503 and "private" not in failed.text
    assert amounts(owner) == (len(DATA), 0)
    endpoint = f"/api/documents/{saved['id']}"
    assert web.get(endpoint + "/download").content == DATA
    assert save(web, saved, payload).json()["error"]["code"] == "operation_aborted"
    monkeypatch.setattr(Storage, "_finish", finish)
    assert save(web, saved, payload, "fresh").status_code == 201


def test_plain_native_document_and_invalid_request_or_protected_content():
    owner, web, saved, payload = start()
    endpoint = f"/api/documents/{saved['id']}/versions"
    for data in (b"{broken", b"{}"):
        result = web.post(
            endpoint,
            content=data,
            headers={
                "Content-Type": "application/json",
                "Idempotency-Key": "bad-json",
            },
        )
        assert (
            result.status_code == 422
            and result.json()["error"]["code"] == "invalid_request"
        )
    changed = deepcopy(payload)
    changed["document"] = DocxPackage(DATA).model
    locked = next(
        node for node in walk(changed["document"]) if node["type"] == "lockedInline"
    )
    locked["attrs"]["label"] = "Private unsupported replacement"
    failed = save(web, saved, changed, "protected")
    assert failed.status_code == 422 and "Private" not in failed.text
    assert amounts(owner) == (len(DATA), 0)
    changed["document"] = DocxPackage(DATA).model
    completed = save(web, saved, changed, "native")
    assert completed.status_code == 201, completed.text
    assert completed.json()["saved_digest"] == saved["digest"]
    with database().connect() as connection:
        assert (
            connection.execute(
                select(versions.c.field_review).where(versions.c.number == 2)
            ).scalar_one()
            is None
        )


def test_local_manual_review_binds_once_without_mutating_request_or_history():
    owner, web, saved, payload = start()
    model = DocxPackage(DATA).model
    manual = {
        "type": "field",
        "attrs": {"id": "a" * 32, "key": "a" * 32, "label": "Раннє поле Їжака"},
        "content": [{"type": "text", "text": "Їжак"}],
    }
    model["content"][0]["content"][0]["content"].append(manual)
    fields = [node for node in walk(model) if node["type"] == "field"]
    model["attrs"] = {
        "review": {
            "sourceVersion": None,
            "items": [
                dict(
                    id="candidate:" + node["attrs"]["id"],
                    occurrenceId=node["attrs"]["id"],
                    reason="manual" if node is manual else "native_control",
                    sourceKey=None,
                    context="",
                    label=node["attrs"]["label"],
                    key=node["attrs"]["key"],
                    type="text",
                    decision="accepted",
                    missing=False,
                    location={"kind": "control", "id": node["attrs"]["id"]},
                )
                for node in fields
            ],
        }
    }
    payload["document"] = model
    before = deepcopy(payload)
    first = save(web, saved, payload)
    assert first.status_code == 201, first.text
    endpoint = f"/api/documents/{saved['id']}/content"
    persisted = web.get(endpoint).json()["document"]
    assert persisted["attrs"]["review"]["sourceVersion"] == saved["current_version_id"]
    assert persisted["attrs"]["review"]["items"] == model["attrs"]["review"]["items"]
    assert payload == before
    # A still-mounted editor may retain a null-origin undo state after acknowledgment.
    payload["source_version_id"] = first.json()["saved_version_id"]
    second = save(web, first.json()["resource"], payload, "local-again")
    assert second.status_code == 201, second.text
    assert (
        web.get(endpoint).json()["document"]["attrs"]["review"]["sourceVersion"]
        == saved["current_version_id"]
    )
    assert payload["document"]["attrs"]["review"]["sourceVersion"] is None
    assert amounts(owner)[1] == 0
