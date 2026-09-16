from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, update
from test_accounts import PASSWORD, account, browser
from test_accounts import account_database as account_database
from test_document_persistence import DATA, client, upload
from test_document_persistence import document_store as document_store

from app.accounts import service as account_service
from app.accounts.schema import AccountInput
from app.documents import deletion, trash
from app.documents.schema import resources, versions
from app.errors import AppError
from app.infrastructure import database
from app.storage.filesystem import FileSystem
from app.storage.schema import accounts


def used(owner):
    with database().connect() as connection:
        return connection.execute(
            select(accounts.c.used_bytes).where(accounts.c.user_id == owner.id)
        ).scalar_one()


def test_trash_restore_preserves_bytes_versions_deadline_and_owner_isolation():
    owner = account()
    web = client()
    saved = upload(web).json()
    identity = UUID(saved["id"])
    endpoint = "/api/documents/" + saved["id"]
    assert browser().post(endpoint + "/trash").status_code == 401
    assert (
        web.post(endpoint + "/trash", headers={"X-CSRF-Token": "bad"}).status_code
        == 403
    )
    account_service.provision(
        AccountInput(login="peer", display_name="Peer", password=PASSWORD)
    )
    peer = browser()
    peer.post("/api/auth/login", json={"login": "peer", "password": PASSWORD})
    assert peer.post(endpoint + "/trash").status_code == 404
    assert web.post(endpoint + "/trash").status_code == 200
    rows = web.get("/api/documents", params={"kind": "trash"}).json()["items"]
    assert len(rows) == 1
    deadline = rows[0]["purge_after"]
    assert used(owner) == len(DATA)
    assert web.post(endpoint + "/trash").status_code == 200
    assert (
        web.get("/api/documents", params={"kind": "trash"}).json()["items"][0][
            "purge_after"
        ]
        == deadline
    )
    assert web.get("/api/documents", params={"kind": "template"}).json()["items"] == []
    assert web.get(endpoint).status_code == 404
    assert web.get(endpoint + "/download").status_code == 404
    assert peer.get("/api/documents", params={"kind": "trash"}).json()["items"] == []
    assert peer.post(endpoint + "/untrash").status_code == 404
    with database().connect() as connection:
        row = (
            connection.execute(select(resources).where(resources.c.id == identity))
            .mappings()
            .one()
        )
        assert row["purge_after"] - row["trashed_at"] == timedelta(days=30)
        assert connection.execute(
            select(versions.c.document_model).where(versions.c.document_id == identity)
        ).scalar_one()
    assert trash.expire() == 0
    assert web.post(endpoint + "/untrash").status_code == 200
    assert web.post(endpoint + "/untrash").status_code == 200
    restored = web.get(endpoint).json()
    assert restored["current_version_id"] == saved["current_version_id"]
    assert restored["trashed_at"] is None
    assert used(owner) == len(DATA)
    assert web.get(endpoint + "/download").content == DATA
    # A stale expiry selection must recheck state under the account lock.
    assert deletion.purge(owner.id, identity, expired_only=True).status == "complete"
    assert web.get(endpoint).status_code == 200
    assert web.post(endpoint + "/trash").status_code == 200
    assert deletion.purge(owner.id, identity, expired_only=True).status == "complete"
    assert used(owner) == len(DATA)
    assert web.delete(endpoint).status_code == 200
    assert web.post(endpoint + "/untrash").status_code == 404
    assert used(owner) == 0
    anonymous = account_service.SessionState("", None, None)
    for operation in [trash.move, trash.restore]:
        with pytest.raises(AppError):
            operation(anonymous, uuid4())
    with pytest.raises(AppError):
        trash.empty(anonymous)


def test_expiry_and_empty_trash_retain_charges_on_failed_unlink(monkeypatch):
    owner = account()
    web = client()
    saved = upload(web).json()
    kept = upload(web, key="kept").json()
    endpoint = "/api/documents/" + saved["id"]
    assert web.post(endpoint + "/trash").status_code == 200
    with database().begin() as connection:
        connection.execute(
            update(resources)
            .where(resources.c.id == UUID(saved["id"]))
            .values(purge_after=func.now())
        )
    assert web.post(endpoint + "/untrash").status_code == 409
    with monkeypatch.context() as patch:
        patch.setattr(
            FileSystem, "remove", lambda *args: (_ for _ in ()).throw(OSError("busy"))
        )
        assert web.delete("/api/documents/trash").json() == {"status": "pending"}
        assert used(owner) == 2 * len(DATA)
        assert web.get("/api/documents", params={"kind": "trash"}).json()["items"][0][
            "deletion_pending"
        ]
    assert web.delete(endpoint).json() == {"status": "complete"}
    assert web.delete("/api/documents/trash").json() == {"status": "complete"}
    assert used(owner) == len(DATA)
    assert web.get("/api/documents/" + kept["id"]).status_code == 200
    assert web.post("/api/documents/" + kept["id"] + "/trash").status_code == 200
    with database().begin() as connection:
        connection.execute(
            update(resources)
            .where(resources.c.id == UUID(kept["id"]))
            .values(purge_after=func.now())
        )
    assert trash.expire(batch=1) == 1
    assert used(owner) == 0


def test_restore_and_empty_trash_serialize_without_losing_a_restored_document():
    owner = account()
    web = client()
    saved = upload(web).json()
    endpoint = "/api/documents/" + saved["id"]
    web.post(endpoint + "/trash")
    peer = client()
    with ThreadPoolExecutor(max_workers=2) as pool:
        restore = pool.submit(web.post, endpoint + "/untrash")
        empty = pool.submit(peer.delete, "/api/documents/trash")
        restored = restore.result()
        assert empty.result().status_code == 200
    if restored.status_code == 200:
        assert web.get(endpoint).status_code == 200
        assert used(owner) == len(DATA)
    else:
        assert restored.status_code in (404, 409)
        assert web.get(endpoint).status_code == 404
        assert used(owner) == 0


def test_trash_migration_downgrade_refuses_recoverable_documents():
    account()
    web = client()
    saved = upload(web).json()
    endpoint = "/api/documents/" + saved["id"]
    web.post(endpoint + "/trash")
    with pytest.raises(RuntimeError, match="Recoverable"):
        command.downgrade(Config("alembic.ini"), "0013_maintenance_state")
    web.post(endpoint + "/untrash")
    command.downgrade(Config("alembic.ini"), "0013_maintenance_state")
    command.upgrade(Config("alembic.ini"), "head")
    assert web.get(endpoint).status_code == 200
