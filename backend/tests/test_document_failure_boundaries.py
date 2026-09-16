"""Incomplete storage and stale metadata must fail without publishing revisions."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from test_accounts import account
from test_accounts import account_database as account_database
from test_document_persistence import DATA, client, counts, upload
from test_document_persistence import document_store as document_store
from test_document_previews import mark
from test_document_restores import restore
from test_document_saves import save, start
from test_template_copies import amounts

from app.documents import previews, restores, routes, saves, service
from app.documents.package import ARCHIVE_BYTES, InvalidDocument
from app.jobs import routes as job_routes
from app.jobs import worker
from app.storage.schema import audit_events, files
from app.storage.service import StorageError


@pytest.mark.parametrize("operation", ["delete", "process"])
def test_mutation_database_failures_return_private_service_errors(
    monkeypatch, operation
):
    account()
    web = client()
    saved = upload(web).json()
    before = counts()

    def fail(*args):
        raise SQLAlchemyError("private database detail")

    if operation == "delete":
        monkeypatch.setattr(routes.deletion, "remove", fail)
        response = web.delete(f"/api/documents/{saved['id']}")
    else:
        monkeypatch.setattr(job_routes.service, "submit", fail)
        response = web.post(f"/api/documents/{saved['id']}/processing")
    assert response.status_code == 503
    assert "private database detail" not in response.text
    assert counts() == before


def test_oversized_saved_metadata_and_worker_reads_are_rejected(monkeypatch):
    owner = account()
    web = client()
    saved = upload(web).json()
    row = service.saved_row(owner.id, UUID(saved["id"]))
    with service.database().begin() as connection:
        connection.execute(
            update(files)
            .where(files.c.id == row["file_id"])
            .values(size_bytes=ARCHIVE_BYTES + 1)
        )
    with pytest.raises(StorageError, match="storage_failure"):
        service.saved_row(owner.id, UUID(saved["id"]))
    with service.database().begin() as connection:
        connection.execute(
            update(files)
            .where(files.c.id == row["file_id"])
            .values(size_bytes=len(DATA))
        )
    monkeypatch.setattr(worker, "ARCHIVE_BYTES", len(DATA) - 1)
    with pytest.raises(InvalidDocument, match="archive_limit"):
        worker.inspect_file(
            owner.id, row["file_id"], "fixture.docx", UUID(saved["current_version_id"])
        )


@pytest.mark.parametrize("operation", ["download", "restore", "save"])
def test_metadata_changes_between_authorization_and_read_fail_closed(
    monkeypatch, operation
):
    owner, web, saved, payload = start()
    before = amounts(owner)
    module = {"download": service, "restore": restores, "save": saves}[operation]
    original = module.saved_row

    def changed(*args, **kwargs):
        row = dict(original(*args, **kwargs))
        if operation == "save":
            row["current_version_id"] = uuid4()
        else:
            row["size_bytes"] += 1
        return row

    monkeypatch.setattr(module, "saved_row", changed)
    if operation == "download":
        response = web.get(f"/api/documents/{saved['id']}/download")
    elif operation == "restore":
        response = restore(web, saved, saved["current_version_id"], payload)
    else:
        response = save(web, saved, payload)
    assert response.status_code == (409 if operation == "save" else 503)
    assert amounts(owner) == before
    assert (
        web.get(f"/api/documents/{saved['id']}").json()["current_version_id"]
        == saved["current_version_id"]
    )


def test_preview_receipt_rolls_back_if_saved_file_is_not_available():
    owner = account()
    web = client()
    saved = upload(web).json()
    row = service.saved_row(owner.id, UUID(saved["id"]))
    with previews.database().begin() as connection:
        connection.execute(
            update(files)
            .where(files.c.id == row["file_id"])
            .values(state="pending_delete")
        )
    assert mark(web, saved).status_code == 404
    with previews.database().connect() as connection:
        assert (
            connection.execute(
                select(audit_events.c.id).where(
                    audit_events.c.id == UUID(saved["current_version_id"])
                )
            ).first()
            is None
        )
