from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert, select, update
from sqlalchemy.exc import SQLAlchemyError
from test_accounts import PASSWORD, account, browser
from test_accounts import account_database as account_database
from test_document_package import walk
from test_document_persistence import DATA, client, upload
from test_document_persistence import document_store as document_store

from app.accounts import service as accounts_service
from app.accounts.schema import AccountInput
from app.documents import copies, routes
from app.documents.export import DocxExport
from app.documents.package import DocxPackage
from app.documents.schema import resources, versions
from app.infrastructure import database
from app.storage.configuration import configured
from app.storage.quotas import set_override
from app.storage.schema import accounts
from app.storage.service import Storage, StorageError


def copy(web, saved, key="copy", **changes):
    return web.post(
        f"/api/documents/{saved['id']}/copies",
        json={
            "title": "  Незалежна заява Їжака  ",
            "source_version_id": saved["current_version_id"],
            **changes,
        },
        headers={"Idempotency-Key": key},
    )


def amounts(owner):
    with database().connect() as connection:
        return connection.execute(
            select(accounts.c.used_bytes, accounts.c.reserved_bytes).where(
                accounts.c.user_id == owner.id
            )
        ).one()


def revision(owner, saved):
    package = DocxPackage(DATA)
    for field in (node for node in walk(package.model) if node["type"] == "field"):
        field["content"] = [{"type": "text", "text": "Збережений Їжак"}]
    # Export against a separate immutable source model, then reopen the actual bytes.
    data = DocxExport(DocxPackage(DATA)).render(package.model, package.digest)
    parsed = DocxPackage(data)
    identity = uuid4()

    def finalize(connection, result):
        connection.execute(
            insert(versions).values(
                id=identity,
                document_id=UUID(saved["id"]),
                owner_id=owner.id,
                file_id=result.id,
                number=2,
                document_model=parsed.model,
                unsupported_count=len(parsed.unsupported),
            )
        )
        connection.execute(
            update(resources)
            .where(resources.c.id == UUID(saved["id"]))
            .values(current_version_id=identity)
        )

    configured().store(
        owner.id,
        "source-revision",
        parsed.digest,
        "version",
        [data],
        expected_bytes=len(data),
        finalize=finalize,
    )
    return {**saved, "current_version_id": str(identity)}, data, parsed.model


def test_copy_uses_saved_revision_and_independent_bytes_schema_and_replay():
    owner = account()
    web = client()
    original = upload(web).json()
    saved, data, model = revision(owner, original)
    result = copy(web, saved)
    assert result.status_code == 201, result.text
    target = result.json()
    assert target["kind"] == "document" and target["title"] == "Незалежна заява Їжака"
    assert (
        target["id"] != saved["id"]
        and target["current_version_id"] != saved["current_version_id"]
    )
    assert result.headers["cache-control"] == "no-store"
    url = f"/api/documents/{target['id']}"
    assert web.get(url + "/download").content == data
    assert web.get(url + "/content").json()["document"] == model
    assert amounts(owner) == (len(DATA) + 2 * len(data), 0)
    assert copy(web, saved).json() == target
    with database().connect() as connection:
        rows = connection.execute(select(resources)).mappings().all()
        assert len({row["original_file_id"] for row in rows}) == 2
    assert web.delete(f"/api/documents/{saved['id']}").json()["status"] == "complete"
    assert web.get(url + "/download").content == data
    assert web.get(url + "/content").json()["document"] == model
    assert copy(web, saved).json() == target  # Source no longer exists.
    assert amounts(owner) == (len(data), 0)
    assert web.delete(url).status_code == 200
    assert copy(web, saved).status_code == 404  # Never resurrect a deleted result.


def test_copy_authorization_kind_revision_and_quota_fail_without_retained_target():
    owner = account()
    web = client()
    saved = upload(web).json()
    assert copy(browser(), saved).status_code == 401
    peer = accounts_service.provision(
        AccountInput(email="peer@example.test", display_name="Peer"), PASSWORD
    )
    other = browser()
    login = other.post(
        "/api/auth/login", json={"email": peer.email, "password": PASSWORD}
    )
    other.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert copy(other, saved).status_code == 404
    token = web.headers["X-CSRF-Token"]
    web.headers["X-CSRF-Token"] = "bad"
    assert copy(web, saved).status_code == 403
    web.headers["X-CSRF-Token"] = token
    assert copy(web, saved, title="  ").status_code == 422
    assert (
        copy(web, saved, key="stale", source_version_id=str(uuid4())).status_code == 409
    )
    direct = upload(web, key="direct", kind="document").json()
    assert copy(web, direct, key="kind").status_code == 422
    set_override(owner.id, 2 * len(DATA))
    assert copy(web, saved, key="quota").json()["error"]["code"] == "quota_exceeded"
    assert amounts(owner) == (2 * len(DATA), 0)
    set_override(owner.id, None)
    assert copy(web, saved, key="quota").json()["error"]["code"] == "operation_aborted"
    copied = copy(web, saved, key="new")
    assert copied.status_code == 201
    assert (
        copy(web, saved, key="new", title="Different").json()["error"]["code"]
        == "operation_conflict"
    )


@pytest.mark.parametrize("change", ["revision", "deletion"])
def test_source_change_between_read_and_commit_aborts_target(change, monkeypatch):
    owner = account()
    web = client()
    saved = upload(web).json()
    finish = Storage._finish
    changed = False

    def race(store, *args):
        nonlocal changed
        if not changed:
            changed = True
            if change == "revision":
                revision(owner, saved)
            else:
                assert web.delete(f"/api/documents/{saved['id']}").status_code == 200
        return finish(store, *args)

    monkeypatch.setattr(Storage, "_finish", race)
    result = copy(web, saved)
    assert result.status_code == (409 if change == "revision" else 404)
    assert web.get("/api/documents?kind=document").json()["items"] == []
    assert amounts(owner)[1] == 0


def test_concurrent_copy_and_changed_source_retry_charge_only_once():
    owner = account()
    web = client()
    saved = upload(web).json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: copy(web, saved), range(2)))
    assert all(result.status_code in (201, 409) for result in results)
    target = next(result.json() for result in results if result.status_code == 201)
    assert amounts(owner) == (2 * len(DATA), 0)
    revision(owner, saved)
    assert copy(web, saved).json() == target
    assert web.get(f"/api/documents/{target['id']}/download").content == DATA
    assert len(web.get("/api/documents?kind=document").json()["items"]) == 1


def test_copy_failure_diagnostics_and_admission_release(monkeypatch):
    account()
    web = client()
    saved = upload(web).json()
    assert routes.UPLOAD_SLOTS.acquire(False) and routes.UPLOAD_SLOTS.acquire(False)
    try:
        assert copy(web, saved).status_code == 429
    finally:
        routes.UPLOAD_SLOTS.release()
        routes.UPLOAD_SLOTS.release()
    for error in (
        StorageError("operation_in_progress"),
        StorageError("storage_failure"),
        SQLAlchemyError("private document text"),
    ):

        def fail(*args):
            raise error

        monkeypatch.setattr(copies, "create", fail)
        response = copy(web, saved)
        assert response.status_code in (409, 503)
        assert "private" not in response.text
        assert response.headers["cache-control"] == "no-store"
    assert routes.UPLOAD_SLOTS.acquire(False)
    routes.UPLOAD_SLOTS.release()
