from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert, select, update
from test_accounts import PASSWORD, account, browser
from test_accounts import account_database as account_database
from test_document_persistence import DATA, client, upload
from test_document_persistence import document_store as document_store

from app.accounts import service as accounts_service
from app.accounts.schema import AccountInput
from app.documents import deletion
from app.documents.schema import resources, versions
from app.infrastructure import database
from app.storage.configuration import configured
from app.storage.filesystem import FileSystem
from app.storage.maintenance import reconcile
from app.storage.schema import accounts, audit_events, files


def usage(owner):
    with database().connect() as connection:
        return connection.execute(
            select(accounts.c.used_bytes).where(accounts.c.user_id == owner.id)
        ).scalar_one()


def test_delete_all_retained_versions_is_owned_confirmed_and_idempotent():
    owner = account()
    web = client()
    saved = upload(web).json()
    another = upload(web, key="keep").json()
    with database().connect() as connection:
        original = (
            connection.execute(
                select(versions).where(versions.c.document_id == UUID(saved["id"]))
            )
            .mappings()
            .one()
        )
    version_id = uuid4()

    def finalize(connection, file):
        connection.execute(
            insert(versions).values(
                **{
                    k: original[k]
                    for k in (
                        "document_id",
                        "owner_id",
                        "document_model",
                        "unsupported_count",
                    )
                },
                id=version_id,
                number=2,
                file_id=file.id,
            )
        )
        connection.execute(
            update(resources)
            .where(resources.c.id == original["document_id"])
            .values(current_version_id=version_id)
        )

    store = configured()
    store.store(
        owner.id,
        "another-version",
        "a" * 64,
        "version",
        [DATA],
        expected_bytes=len(DATA),
        finalize=finalize,
    )
    url = "/api/documents/" + saved["id"]
    assert browser().delete(url).status_code == 401
    assert web.delete(url, headers={"X-CSRF-Token": "bad"}).status_code == 403
    other = accounts_service.provision(
        AccountInput(email="other@example.test", display_name="Other"), PASSWORD
    )
    peer = browser()
    login = peer.post(
        "/api/auth/login", json={"email": other.login, "password": PASSWORD}
    )
    peer.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert peer.delete(url).status_code == 404
    assert usage(owner) == 3 * len(DATA)
    response = web.delete(url)
    assert response.json() == {"status": "complete"}
    assert response.headers["cache-control"] == "no-store"
    assert web.delete(url).json() == {"status": "complete"}
    assert usage(owner) == len(DATA)
    with database().connect() as connection:
        requests = connection.execute(
            select(audit_events.c.actor_id, audit_events.c.owner_id).where(
                audit_events.c.action == "document_deletion_requested"
            )
        ).all()
    assert requests == [(owner.id, owner.id)]
    with database().connect() as connection:
        models = (
            connection.execute(
                select(versions.c.document_model).where(
                    versions.c.document_id == UUID(saved["id"])
                )
            )
            .scalars()
            .all()
        )
    assert models == [{}, {}]
    assert web.get(url).status_code == 404
    assert web.get(url + "/download").status_code == 404
    assert web.get("/api/documents/" + another["id"] + "/download").content == DATA
    assert [
        row["id"] for row in web.get("/api/documents?kind=template").json()["items"]
    ] == [another["id"]]
    assert web.delete(f"/api/documents/{uuid4()}").status_code == 404
    logout = web.post("/api/auth/logout")
    assert web.delete(url).status_code == 403  # The old session's CSRF is rejected.
    web.headers["X-CSRF-Token"] = logout.json()["csrf_token"]
    assert web.delete(url).status_code == 401


def test_failed_cleanup_stays_charged_visible_and_reconciles(monkeypatch):
    owner = account()
    web = client()
    saved = upload(web).json()
    url = "/api/documents/" + saved["id"]
    remove = FileSystem.remove
    monkeypatch.setattr(
        FileSystem,
        "remove",
        lambda *args: (_ for _ in ()).throw(OSError("private path")),
    )
    assert web.delete(url).json() == {"status": "pending"}
    assert web.delete(url).json() == {"status": "pending"}
    assert usage(owner) == len(DATA)
    listed = client().get("/api/documents?kind=template").json()["items"]
    assert len(listed) == 1 and listed[0]["deletion_pending"] is True
    assert web.get(url + "/download").status_code == 404
    monkeypatch.setattr(FileSystem, "remove", remove)
    assert reconcile(configured())["operations"][0]["status"] == "deleted"
    assert usage(owner) == 0
    assert web.get("/api/documents?kind=template").json()["items"] == []
    assert web.delete(url).json() == {"status": "complete"}


def test_active_reader_defers_cleanup_and_concurrent_retries_charge_once():
    owner = account()
    web = client()
    saved = upload(web).json()
    url = "/api/documents/" + saved["id"]
    with database().connect() as connection:
        file_id = connection.execute(select(files.c.id)).scalar_one()
    with configured().read(owner.id, file_id) as stream:
        assert web.delete(url).json() == {"status": "pending"}
        assert stream.read() == DATA
        assert usage(owner) == len(DATA)
    peer = client()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda candidate: candidate.delete(url).json(), [web, peer])
        )
    assert all(result["status"] in ("pending", "complete") for result in results)
    assert web.delete(url).json() == {"status": "complete"}
    assert usage(owner) == 0


def test_shared_references_are_rejected_and_revoked_service_state_is_fenced():
    owner = account()
    web = client()
    first = upload(web).json()
    second = upload(web, key="second").json()
    with database().begin() as connection:
        original = connection.execute(
            select(resources.c.original_file_id).where(
                resources.c.id == UUID(first["id"])
            )
        ).scalar_one()
        connection.execute(
            update(resources)
            .where(resources.c.id == UUID(second["id"]))
            .values(original_file_id=original)
        )
    assert web.delete("/api/documents/" + first["id"]).status_code == 409
    assert usage(owner) == len(DATA) * 2
    state = accounts_service.read_session(web.cookies.get("fillable_session_v1"))
    web.post("/api/auth/logout")
    from app.errors import AppError

    with pytest.raises(AppError) as error:
        deletion.remove(state, UUID(second["id"]))
    assert error.value.status == 401
