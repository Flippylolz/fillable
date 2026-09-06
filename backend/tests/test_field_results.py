from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from test_accounts import PASSWORD, account, browser
from test_accounts import account_database as account_database
from test_document_persistence import client, upload
from test_document_persistence import document_store as document_store
from test_processing import processing_store as processing_store
from test_processing import row, start
from test_template_copies import amounts, copy

from app.accounts import service as accounts_service
from app.accounts.schema import AccountInput
from app.infrastructure import database
from app.jobs import dispatcher, service, worker
from app.jobs.schema import jobs
from app.storage.service import now


def test_real_result_is_owned_revision_bound_and_copied_without_processing_again():
    owner, web, saved, url, job = start()
    endpoint = f"/api/documents/{saved['id']}/fields"
    assert web.get(endpoint).json() == {
        "source_version_id": saved["current_version_id"],
        "status": "queued",
        "snapshot": None,
    }
    assert browser().get(endpoint).status_code == 401
    peer = accounts_service.provision(
        AccountInput(email="peer@example.test", display_name="Peer"), PASSWORD
    )
    other = browser()
    login = other.post(
        "/api/auth/login", json={"email": peer.email, "password": PASSWORD}
    )
    other.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert other.get(endpoint).status_code == 404
    assert web.get(f"/api/documents/{uuid4()}/fields").status_code == 404
    before = amounts(owner)
    worker.process(job["id"], 1)
    result = web.get(endpoint)
    assert result.headers["cache-control"] == "no-store"
    snapshot = result.json()["snapshot"]
    assert len(snapshot["candidates"]) == 28
    assert snapshot["source_version_id"] == saved["current_version_id"]
    assert web.get(url).json()["summary"]["field_candidates"] == 28
    assert "snapshot" not in web.get(url).json()  # Polling remains content-free.
    assert amounts(owner) == before
    target = copy(web, saved).json()
    target_endpoint = f"/api/documents/{target['id']}/fields"
    cloned = web.get(target_endpoint).json()
    assert cloned["status"] == "succeeded"
    assert cloned["snapshot"] == {
        **snapshot,
        "source_version_id": target["current_version_id"],
    }
    with database().connect() as connection:
        target_job = (
            connection.execute(
                select(jobs).where(jobs.c.document_id == UUID(target["id"]))
            )
            .mappings()
            .one()
        )
        assert target_job["id"] != UUID(job["id"])
        assert target_job["dispatched_at"] is None
    assert dispatcher.dispatch()["enqueued"] == 0
    assert web.delete(f"/api/documents/{saved['id']}").json()["status"] == "complete"
    assert row(job["id"])["field_snapshot"] is None
    assert web.get(endpoint).status_code == 404
    assert web.get(target_endpoint).json() == cloned
    assert web.get(f"/api/documents/{target['id']}/download").status_code == 200
    assert web.delete(f"/api/documents/{target['id']}").status_code == 200
    assert row(str(target_job["id"]))["field_snapshot"] is None


def test_legacy_completed_inspection_can_retry_and_empty_migration_roundtrip():
    account()
    web = client()
    saved = upload(web).json()
    endpoint = f"/api/documents/{saved['id']}/fields"
    command.downgrade(Config("alembic.ini"), "0006_processing_jobs")
    command.upgrade(Config("alembic.ini"), "head")
    with database().begin() as connection:
        connection.execute(
            update(jobs).values(status="succeeded", summary={"paragraphs": 1})
        )
    assert web.get(endpoint).json()["status"] == "not_started"
    retried = web.post(f"/api/documents/{saved['id']}/processing").json()
    assert retried["attempt"] == 2 and retried["status"] == "queued"
    worker.process(retried["id"], 2)
    assert web.get(endpoint).json()["status"] == "succeeded"


def test_expired_and_mismatched_results_cannot_publish_and_failures_are_safe(
    monkeypatch,
):
    owner, web, saved, _, job = start()
    endpoint = f"/api/documents/{saved['id']}/fields"
    claimed = worker.claim(UUID(job["id"]), 1)
    result = worker.inspect_file(*claimed)
    result["field_snapshot"]["source_version_id"] = str(uuid4())
    with pytest.raises(ValueError, match="stale_field_snapshot"):
        worker.finish(UUID(job["id"]), 1, result)
    assert row(job["id"])["field_snapshot"] is None
    result["field_snapshot"]["source_version_id"] = saved["current_version_id"]
    with database().begin() as connection:
        connection.execute(
            update(jobs).values(lease_until=now() - timedelta(seconds=1))
        )
    worker.finish(UUID(job["id"]), 1, result)
    assert row(job["id"])["field_snapshot"] is None
    dispatcher.dispatch()
    worker.process(job["id"], 2)
    assert web.get(endpoint).json()["status"] == "succeeded"
    with database().begin() as connection:
        connection.execute(
            update(jobs).values(field_snapshot={"source_version_id": str(uuid4())})
        )
    response = web.get(endpoint)
    assert (
        response.status_code == 503
        and response.json()["error"]["code"] == "dependencies_unavailable"
    )

    before = amounts(owner)
    rejected = copy(web, saved, key="invalid-metadata")
    assert rejected.status_code == 503
    assert amounts(owner) == before

    def fail(*args):
        raise SQLAlchemyError("private field contents")

    monkeypatch.setattr(service, "fields", fail)
    response = web.get(endpoint)
    assert response.status_code == 503 and "private" not in response.text
