from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from test_accounts import PASSWORD, browser
from test_accounts import account_database as account_database
from test_document_persistence import DATA, upload
from test_document_persistence import document_store as document_store
from test_document_saves import save, start
from test_template_copies import amounts, copy, revision

from app.accounts import service as accounts_service
from app.accounts.schema import AccountInput, sessions, users
from app.documents import restores, routes
from app.documents.lease_schema import leases
from app.documents.package import DocxPackage
from app.documents.schema import resources, versions
from app.infrastructure import database
from app.jobs import worker
from app.jobs.schema import jobs
from app.storage.quotas import set_override
from app.storage.schema import files
from app.storage.service import Storage, StorageError, now


def restore(web, resource, selected, payload, key="restore"):
    return web.post(
        f"/api/documents/{resource['id']}/versions/{selected}/restore",
        json={
            name: payload[name]
            for name in ("source_version_id", "client_id", "lease_id")
        },
        headers={"Idempotency-Key": key},
    )


@pytest.mark.parametrize("kind", ["template", "document"])
def test_restore_original_and_reviewed_pairs_preserves_history_and_independent_copies(
    kind,
):
    owner, web, original, payload = start(kind)
    first = save(web, original, payload).json()
    endpoint = f"/api/documents/{original['id']}"
    edited_bytes = web.get(endpoint + "/download").content
    independent = copy(web, first["resource"]).json() if kind == "template" else None
    before = amounts(owner)
    payload["source_version_id"] = first["saved_version_id"]
    response = restore(web, original, original["current_version_id"], payload)
    assert response.status_code == 201, response.text
    reverted = response.json()
    assert reverted["saved_number"] == 3
    assert response.headers["cache-control"] == "no-store"
    assert web.get(endpoint + "/download").content == DATA
    assert web.get(endpoint + "/content").json()["document"] == DocxPackage(DATA).model
    assert amounts(owner) == (before[0] + len(DATA), 0)
    assert (
        restore(web, original, original["current_version_id"], payload).json()
        == reverted
    )
    payload["source_version_id"] = reverted["saved_version_id"]
    again = restore(
        web, original, first["saved_version_id"], payload, "reviewed"
    ).json()
    assert again["saved_number"] == 4
    assert web.get(endpoint + "/download").content == edited_bytes
    assert web.get(endpoint + "/content").json()["document"] == payload["document"]
    assert amounts(owner) == (before[0] + len(DATA) + len(edited_bytes), 0)
    page = web.get(endpoint + "/versions").json()
    assert [item["number"] for item in page["items"]] == [4, 3, 2, 1]
    assert page["items"][0]["parent_version_id"] == reverted["saved_version_id"]
    assert page["items"][0]["restored_from_version_id"] == first["saved_version_id"]
    assert page["items"][0]["restored_from_number"] == 2
    assert page["items"][2]["parent_version_id"] == original["current_version_id"]
    assert page["items"][2]["restored_from_version_id"] is None
    for selected, expected in (
        (original["current_version_id"], DATA),
        (first["saved_version_id"], edited_bytes),
        (reverted["saved_version_id"], DATA),
    ):
        assert web.get(f"{endpoint}/versions/{selected}/download").content == expected
    with database().connect() as connection:
        assert connection.execute(
            select(leases.c.source_version_id)
        ).scalar_one() == UUID(again["saved_version_id"])
        job = (
            connection.execute(
                select(jobs).where(
                    jobs.c.source_version_id == UUID(again["saved_version_id"])
                )
            )
            .mappings()
            .one()
        )
    worker.process(str(job["id"]), 1)
    assert web.get(endpoint + "/fields").json()["status"] == "succeeded"
    # A later ordinary save uses the restored pair's original source anchors.
    payload["source_version_id"] = again["saved_version_id"]
    follow = save(web, original, payload, "after-restore")
    assert follow.status_code == 201, follow.text
    assert follow.json()["saved_number"] == 5
    if independent:
        assert (
            web.get(f"/api/documents/{independent['id']}/download").content
            == edited_bytes
        )
        assert web.delete(endpoint).status_code == 200
        assert (
            web.get(f"/api/documents/{independent['id']}/download").content
            == edited_bytes
        )


def test_review_only_restore_and_delayed_committed_replay_are_exact(monkeypatch):
    owner, web, original, payload = start()
    first = save(web, original, payload).json()
    changed = deepcopy(payload)
    changed["source_version_id"] = first["saved_version_id"]
    next(
        item
        for item in changed["document"]["attrs"]["review"]["items"]
        if item["decision"] == "proposed"
    )["decision"] = "dismissed"
    second = save(web, original, changed, "review-only").json()
    changed["source_version_id"] = second["saved_version_id"]
    original_finish = Storage._finish

    def lost_response(store, *args):
        original_finish(store, *args)
        raise SQLAlchemyError("private response")

    with monkeypatch.context() as patch:
        patch.setattr(Storage, "_finish", lost_response)
        response = restore(web, original, first["saved_version_id"], changed)
        assert response.status_code == 503 and "private" not in response.text
    endpoint = f"/api/documents/{original['id']}"
    restored = web.get(endpoint).json()
    assert web.get(endpoint + "/content").json()["document"] == payload["document"]
    new_payload = {**payload, "source_version_id": restored["current_version_id"]}
    newest = save(web, original, new_payload, "newer").json()
    before = amounts(owner)

    def forbidden_read(*args, **kwargs):
        raise AssertionError("Committed restore must not reopen selected history")

    monkeypatch.setattr(restores, "saved_row", forbidden_read)
    replay = restore(web, original, first["saved_version_id"], changed)
    assert replay.status_code == 201, replay.text
    assert replay.json()["saved_version_id"] == restored["current_version_id"]
    assert replay.json()["resource"]["current_version_id"] == newest["saved_version_id"]
    assert amounts(owner) == before
    assert (
        restore(web, original, original["current_version_id"], changed).status_code
        == 409
    )


@pytest.mark.parametrize(
    "change",
    [
        "base",
        "client",
        "generation",
        "expired",
        "session",
        "owner",
        "csrf",
        "anonymous",
        "selection",
    ],
)
def test_restore_rejects_stale_or_unowned_requests_without_changing_current(change):
    owner, web, original, payload = start()
    selected = original["current_version_id"]
    before = amounts(owner)
    expected = 409
    if change in ("base", "client", "generation"):
        payload[
            {
                "base": "source_version_id",
                "client": "client_id",
                "generation": "lease_id",
            }[change]
        ] = str(uuid4())
    elif change in ("expired", "session"):
        with database().begin() as connection:
            connection.execute(
                update(leases if change == "expired" else sessions).values(
                    expires_at=now() - timedelta(seconds=1)
                )
            )
        if change == "session":
            expected = 401
    elif change == "owner":
        other = accounts_service.provision(
            AccountInput(
                email="other@example.test", display_name="Other", role="admin"
            ),
            PASSWORD,
        )
        web = browser()
        login = web.post(
            "/api/auth/login", json={"email": other.login, "password": PASSWORD}
        )
        web.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        expected = 404
    elif change == "csrf":
        web.headers["X-CSRF-Token"] = "bad"
        expected = 403
    elif change == "anonymous":
        web = browser()
        expected = 401
    else:
        selected = upload(web, key="other").json()["current_version_id"]
        before = amounts(owner)
        expected = 404
    response = restore(web, original, selected, payload)
    assert response.status_code == expected, response.text
    assert amounts(owner) == before
    with database().connect() as connection:
        assert connection.execute(
            select(resources.c.current_version_id).where(
                resources.c.id == UUID(original["id"])
            )
        ).scalar_one() == UUID(original["current_version_id"])


@pytest.mark.parametrize(
    "race", ["lease", "quota", "revision", "deletion", "revocation", "selected"]
)
def test_restore_finalization_rechecks_current_authority_and_selected_retention(
    race, monkeypatch
):
    owner, web, original, payload = start()
    finish = Storage._finish
    entered = False

    def changed_finish(store, *args):
        nonlocal entered
        if not entered:
            entered = True
            if race == "quota":
                set_override(owner.id, len(DATA))
            elif race == "revision":
                revision(owner, original)
            elif race == "deletion":
                assert web.delete(f"/api/documents/{original['id']}").status_code == 200
            else:
                with database().begin() as connection:
                    if race == "lease":
                        connection.execute(update(leases).values(lease_id=uuid4()))
                    elif race == "revocation":
                        connection.execute(update(users).values(active=False))
                    else:
                        connection.execute(
                            update(files)
                            .where(files.c.state == "ready")
                            .values(state="pending_delete")
                        )
        return finish(store, *args)

    monkeypatch.setattr(Storage, "_finish", changed_finish)
    response = restore(web, original, original["current_version_id"], payload)
    assert response.status_code in (401, 404, 409), response.text
    assert amounts(owner)[1] == 0
    with database().connect() as connection:
        rows = connection.execute(select(versions)).mappings().all()
        assert len(rows) == (2 if race == "revision" else 1)
        assert all(row["restored_from_version_id"] is None for row in rows)


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_restores_allocate_one_new_revision(same_key):
    owner, web, original, payload = start()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda index: restore(
                    web,
                    original,
                    original["current_version_id"],
                    payload,
                    "same" if same_key else str(index),
                ),
                range(2),
            )
        )
    assert all(response.status_code in (201, 409) for response in results)
    assert any(response.status_code == 201 for response in results)
    assert amounts(owner) == (2 * len(DATA), 0)
    with database().connect() as connection:
        assert len(connection.execute(select(versions)).all()) == 2


def test_restore_corrupt_model_or_bytes_and_disk_failure_keep_previous_pair(
    document_store, monkeypatch
):
    owner, web, original, payload = start()
    with database().connect() as connection:
        file_id = connection.execute(select(versions.c.file_id)).scalar_one()
    path = document_store / "files" / str(owner.id) / str(file_id)
    path.chmod(0o600)
    path.write_bytes(b"corrupt")
    assert (
        restore(web, original, original["current_version_id"], payload).status_code
        == 503
    )
    path.write_bytes(DATA)
    with database().begin() as connection:
        connection.execute(update(versions).values(document_model={}))
    assert (
        restore(
            web, original, original["current_version_id"], payload, "model"
        ).status_code
        == 503
    )
    with database().begin() as connection:
        connection.execute(
            update(versions).values(document_model=DocxPackage(DATA).model)
        )

    def full_disk(*args):
        raise OSError("private disk failure")

    with monkeypatch.context() as patch:
        patch.setattr(Storage, "_finish", full_disk)
        response = restore(
            web, original, original["current_version_id"], payload, "disk"
        )
        assert response.status_code == 503 and "private" not in response.text
    assert amounts(owner) == (len(DATA), 0)
    assert (
        restore(
            web, original, original["current_version_id"], payload, "disk"
        ).status_code
        == 409
    )
    assert (
        restore(
            web, original, original["current_version_id"], payload, "fresh"
        ).status_code
        == 201
    )


def test_restore_admission_invalid_body_and_safe_storage_failures(monkeypatch):
    owner, web, original, payload = start()
    selected = original["current_version_id"]
    routes.UPLOAD_SLOTS.acquire()
    routes.UPLOAD_SLOTS.acquire()
    try:
        assert restore(web, original, selected, payload).status_code == 429
    finally:
        routes.UPLOAD_SLOTS.release()
        routes.UPLOAD_SLOTS.release()
    endpoint = f"/api/documents/{original['id']}/versions/{selected}/restore"
    assert (
        web.post(endpoint, json={}, headers={"Idempotency-Key": "invalid"}).status_code
        == 422
    )
    for code, status in (
        ("not_found", 404),
        ("operation_in_progress", 409),
        ("quota_exceeded", 409),
        ("file_too_large", 413),
    ):
        with monkeypatch.context() as patch:

            def fail(*args):
                raise StorageError(code)

            patch.setattr(restores, "restore", fail)
            response = restore(web, original, selected, payload)
            assert response.status_code == status
    assert amounts(owner) == (len(DATA), 0)
    assert restore(web, original, selected, payload).status_code == 201


def test_provenance_migration_backfills_and_guards_cross_document_links():
    owner, web, original, _ = start()
    revision(owner, original)
    other = upload(web, key="other").json()
    config = Config("alembic.ini")
    command.downgrade(config, "0009_saved_review")
    command.upgrade(config, "head")
    with database().connect() as connection:
        second = (
            connection.execute(select(versions).where(versions.c.number == 2))
            .mappings()
            .one()
        )
        assert second["parent_version_id"] == UUID(original["current_version_id"])
        assert second["restored_from_version_id"] is None
    for column in ("parent_version_id", "restored_from_version_id"):
        with pytest.raises(IntegrityError), database().begin() as connection:
            connection.execute(
                update(versions)
                .where(versions.c.id == second["id"])
                .values(**{column: UUID(other["current_version_id"])})
            )
    with pytest.raises(RuntimeError, match="refusing destructive downgrade"):
        command.downgrade(config, "0009_saved_review")
    with database().begin() as connection:
        connection.execute(update(versions).values(parent_version_id=None))
    command.downgrade(config, "0009_saved_review")
    command.upgrade(config, "head")


def test_save_and_restore_race_can_commit_only_one_current_successor():
    owner, web, original, payload = start()
    with ThreadPoolExecutor(max_workers=2) as pool:
        saving = pool.submit(save, web, original, payload)
        restoring = pool.submit(
            restore, web, original, original["current_version_id"], payload
        )
        responses = [saving.result(), restoring.result()]
    assert sorted(response.status_code for response in responses) == [201, 409]
    successful = next(
        response.json() for response in responses if response.status_code == 201
    )
    assert amounts(owner) == (len(DATA) + successful["saved_size_bytes"], 0)
    with database().connect() as connection:
        assert len(connection.execute(select(versions)).all()) == 2
        assert connection.execute(
            select(resources.c.current_version_id)
        ).scalar_one() == UUID(successful["saved_version_id"])


def test_deleted_restore_result_is_not_recreated_by_retry():
    owner, web, original, payload = start()
    assert (
        restore(web, original, original["current_version_id"], payload).status_code
        == 201
    )
    assert web.delete(f"/api/documents/{original['id']}").status_code == 200
    assert amounts(owner) == (0, 0)
    assert (
        restore(web, original, original["current_version_id"], payload).status_code
        == 404
    )
    assert amounts(owner) == (0, 0)
    with database().connect() as connection:
        rows = connection.execute(select(versions)).mappings().all()
        assert len(rows) == 2 and all(row["document_model"] == {} for row in rows)
        assert rows[0]["id"] != rows[1]["id"]
