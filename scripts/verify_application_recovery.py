"""Synthetic QA only: saved history, image upgrade and crash reconciliation."""

import base64
import hashlib
import json
import os
import sys
import time
from copy import deepcopy
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select

from app.accounts.service import read_session
from app.documents.deletion import remove
from app.documents.schema import resources, versions
from app.infrastructure import database
from app.storage.configuration import configured
from app.storage.filesystem import FileSystem
from app.storage.schema import accounts, files, reservations

EMAIL = "upgrade-proof@example.test"
PASSWORD = "Synthetic-browser-Їжак-2026"
ORIGIN = os.environ["FILLABLE_PUBLIC_ORIGIN"]


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    return hashlib.sha256(value).hexdigest()


def request(client, method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response


def authenticate():
    client = httpx.Client(base_url=ORIGIN, headers={"Origin": ORIGIN}, timeout=40)
    bootstrap = request(client, "GET", "/api/auth/session").json()
    client.headers["X-CSRF-Token"] = bootstrap["csrf_token"]
    signed = request(
        client, "POST", "/api/auth/login", json={"email": EMAIL, "password": PASSWORD}
    ).json()
    assert signed["user"]["email"] == EMAIL
    client.headers["X-CSRF-Token"] = signed["csrf_token"]
    return client, signed["user"]["id"]


def upload(client, key, title):
    data = Path("/tmp/recovery-source.docx").read_bytes()
    return request(
        client,
        "POST",
        "/api/documents",
        content=data,
        headers={
            "Content-Type": (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
            "Idempotency-Key": key,
            "X-Upload-Metadata": base64.b64encode(
                json.dumps(
                    {
                        "kind": "template",
                        "filename": "Синтетичний.docx",
                        "title": title,
                    },
                    ensure_ascii=False,
                ).encode()
            ).decode(),
        },
    ).json()


def lease(client, resource):
    tab = str(uuid4())
    current = request(
        client,
        "POST",
        f"/api/documents/{resource['id']}/editing-lease",
        json={
            "action": "acquire",
            "client_id": tab,
            "source_version_id": resource["current_version_id"],
            "lease_id": None,
        },
    ).json()
    return {
        "client_id": tab,
        "lease_id": current["lease_id"],
        "source_version_id": resource["current_version_id"],
    }


def save(client, resource, fence, model, key):
    result = request(
        client,
        "POST",
        f"/api/documents/{resource['id']}/versions",
        json={**fence, "document": model},
        headers={"Idempotency-Key": key},
    ).json()
    fence["source_version_id"] = result["saved_version_id"]
    return result["resource"]


def walk(node):
    yield node
    for child in node.get("content", []):
        yield from walk(child)


def capture(client, owner, identities):
    result = {"owner": owner, "resources": {}}
    with database().connect() as connection:
        account = (
            connection.execute(
                select(accounts).where(accounts.c.user_id == UUID(owner))
            )
            .mappings()
            .one()
        )
        result["usage"] = {
            key: account[key]
            for key in ("used_bytes", "reserved_bytes", "override_bytes")
        }
        assert result["usage"]["reserved_bytes"] == 0
        for identity in identities:
            endpoint = f"/api/documents/{identity}"
            resource = (
                connection.execute(
                    select(resources).where(
                        resources.c.id == UUID(identity),
                        resources.c.owner_id == UUID(owner),
                    )
                )
                .mappings()
                .one()
            )
            assert resource["state"] == "active"
            page = request(client, "GET", endpoint + "/versions").json()
            assert (
                page["next_before"] is None and page["retention"]["keep_latest"] is None
            )
            current = request(client, "GET", endpoint + "/content").json()["document"]
            histories = []
            for entry in page["items"]:
                selected = endpoint + f"/versions/{entry['id']}"
                model = request(client, "GET", selected + "/content").json()["document"]
                data = request(client, "GET", selected + "/download").content
                row = (
                    connection.execute(
                        select(versions).where(versions.c.id == UUID(entry["id"]))
                    )
                    .mappings()
                    .one()
                )
                stored = (
                    connection.execute(
                        select(files).where(files.c.id == row["file_id"])
                    )
                    .mappings()
                    .one()
                )
                assert stored["owner_id"] == UUID(owner) and stored["state"] == "ready"
                assert stored["digest"] == digest(data) and stored["size_bytes"] == len(
                    data
                )
                with configured().read(UUID(owner), row["file_id"]) as stream:
                    assert stream.read() == data
                paired = deepcopy(row["document_model"])
                if row["field_review"] is not None:
                    paired["attrs"] = {"review": row["field_review"]}
                assert model == paired
                histories.append(
                    {
                        "id": entry["id"],
                        "number": entry["number"],
                        "file_id": str(row["file_id"]),
                        "digest": digest(data),
                        "bytes": len(data),
                        "model_digest": digest(model),
                        "review_digest": digest(row["field_review"]),
                        "parent": str(row["parent_version_id"])
                        if row["parent_version_id"]
                        else None,
                        "restored_from": str(row["restored_from_version_id"])
                        if row["restored_from_version_id"]
                        else None,
                    }
                )
            with configured().read(UUID(owner), resource["original_file_id"]) as stream:
                original_digest = digest(stream.read())
            result["resources"][identity] = {
                "kind": resource["kind"],
                "title": resource["title"],
                "current": str(resource["current_version_id"]),
                "original": str(resource["original_file_id"]),
                "original_digest": original_digest,
                "current_model_digest": digest(current),
                "download_digest": digest(
                    request(client, "GET", endpoint + "/download").content
                ),
                "versions": histories,
            }
    assert result["usage"]["used_bytes"] == sum(
        entry["bytes"]
        for item in result["resources"].values()
        for entry in item["versions"]
    )
    return result


def write(client, owner):
    source = upload(
        client, "upgrade-template-proof", "Шаблон Ґанни Їжак — перевірка оновлення"
    )
    source_fence = lease(client, source)
    model = json.loads(Path("/tmp/recovery-review.json").read_text())
    model["attrs"]["review"]["sourceVersion"] = source["current_version_id"]
    original = source["current_version_id"]
    source = save(client, source, source_fence, model, "upgrade-reviewed-v2")
    reviewed = source["current_version_id"]
    copy = request(
        client,
        "POST",
        f"/api/documents/{source['id']}/copies",
        json={
            "title": "Незалежна заява Їжака",
            "source_version_id": reviewed,
        },
        headers={"Idempotency-Key": "upgrade-independent-copy"},
    ).json()
    copy_fence = lease(client, copy)
    copy_model = request(client, "GET", f"/api/documents/{copy['id']}/content").json()[
        "document"
    ]
    field = next(node for node in walk(copy_model) if node["type"] == "field")
    for text in field["content"]:
        text["text"] = "Ї" * (len(text["text"].encode("utf-16-le")) // 2)
    copy = save(client, copy, copy_fence, copy_model, "upgrade-independent-edit")
    for number, selected in ((3, original), (4, reviewed)):
        restored = request(
            client,
            "POST",
            f"/api/documents/{source['id']}/versions/{selected}/restore",
            json=source_fence,
            headers={"Idempotency-Key": f"upgrade-restore-{number}"},
        ).json()
        assert restored["saved_number"] == number
        source_fence["source_version_id"] = restored["saved_version_id"]
    result = capture(client, owner, [source["id"], copy["id"]])
    source_history = result["resources"][source["id"]]["versions"]
    assert [entry["number"] for entry in source_history] == [4, 3, 2, 1]
    assert source_history[0]["restored_from"] == reviewed
    assert source_history[0]["model_digest"] == source_history[2]["model_digest"]
    assert source_history[0]["review_digest"] == source_history[2]["review_digest"]
    assert source_history[1]["restored_from"] == original
    copy_history = result["resources"][copy["id"]]["versions"]
    assert [entry["number"] for entry in copy_history] == [2, 1]
    assert copy_history[1]["digest"] == source_history[2]["digest"]
    assert copy_history[0]["digest"] != copy_history[1]["digest"]
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


def crash(client, owner):
    resource = upload(client, "upgrade-crash-proof", "Synthetic crash reconciliation")
    for _ in range(60):
        processing = request(
            client, "GET", f"/api/documents/{resource['id']}/processing"
        ).json()
        if processing["status"] == "succeeded":
            break
        time.sleep(0.5)
    else:
        raise AssertionError("Synthetic crash resource processing did not finish")
    state = read_session(client.cookies.get("fillable_session_v1"))
    assert state is not None and state.user is not None and str(state.user.id) == owner
    with database().connect() as connection:
        expected_file = connection.execute(
            select(resources.c.original_file_id).where(
                resources.c.id == UUID(resource["id"])
            )
        ).scalar_one()
    original_remove = FileSystem.remove

    def interrupted(self, operation, file_owner, file_id):
        assert file_owner == UUID(owner) and file_id == expected_file
        original_remove(self, operation, file_owner, file_id)
        os._exit(74)

    FileSystem.remove = interrupted
    remove(state, UUID(resource["id"]))
    raise AssertionError("Synthetic crash boundary was not reached")


def pending(owner, manifest):
    with database().connect() as connection:
        row = (
            connection.execute(
                select(files)
                .join(reservations, reservations.c.id == files.c.reservation_id)
                .where(
                    reservations.c.owner_id == UUID(owner),
                    reservations.c.idempotency_key == "upload:upgrade-crash-proof",
                )
            )
            .mappings()
            .one()
        )
        assert row["state"] == "pending_delete"
        usage = connection.execute(
            select(accounts.c.used_bytes).where(accounts.c.user_id == UUID(owner))
        ).scalar_one()
        assert usage == manifest["usage"]["used_bytes"] + row["size_bytes"]
    with configured().fs.area("files", UUID(owner)) as directory:
        try:
            os.stat(str(row["id"]), dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("Crash did not occur after unlink")
    print("PASS: crashed deletion remains charged with durable pending metadata")


def main():
    assert os.getuid() == 10001 and ORIGIN == "http://gateway:8080"
    assert sys.argv[1] in ("write", "read", "crash", "pending")
    with database().connect() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT token FROM recovery_verification_guard"
            ).scalar_one()
            == os.environ["RECOVERY_PROOF_NONCE"]
        )
    client, owner = authenticate()
    try:
        if sys.argv[1] == "write":
            write(client, owner)
        elif sys.argv[1] == "crash":
            crash(client, owner)
        else:
            manifest = json.load(sys.stdin)
            assert manifest["owner"] == owner
            if sys.argv[1] == "pending":
                pending(owner, manifest)
            else:
                assert capture(client, owner, list(manifest["resources"])) == manifest
                with database().connect() as connection:
                    deleted = (
                        connection.execute(
                            select(
                                resources.c.id,
                                resources.c.state,
                                files.c.state.label("file_state"),
                            )
                            .join(versions, versions.c.document_id == resources.c.id)
                            .join(files, files.c.id == versions.c.file_id)
                            .join(
                                reservations,
                                reservations.c.id == files.c.reservation_id,
                            )
                            .where(
                                reservations.c.owner_id == UUID(owner),
                                reservations.c.idempotency_key
                                == "upload:upgrade-crash-proof",
                            )
                        )
                        .mappings()
                        .one_or_none()
                    )
                if deleted is not None:
                    assert deleted["state"] == deleted["file_state"] == "deleted"
                    assert (
                        client.get(
                            f"/api/documents/{deleted['id']}/content"
                        ).status_code
                        == 404
                    )
                print(
                    "PASS: original, edited/copy/restored history, paired review, "
                    "ownership and exact quota survived"
                )
        request(client, "POST", "/api/auth/logout")
    finally:
        client.close()


if __name__ == "__main__":
    main()
