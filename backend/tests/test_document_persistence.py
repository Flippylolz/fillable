import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.requests import Request
from test_accounts import PASSWORD, account, browser, sign_in
from test_accounts import account_database as account_database

from app.accounts import service as accounts_service
from app.accounts.schema import AccountInput, sessions
from app.documents import routes, service
from app.documents.schema import resources, versions
from app.errors import AppError
from app.infrastructure import database
from app.storage.filesystem import initialize
from app.storage.quotas import set_override
from app.storage.schema import accounts, audit_events, files, reservations
from app.storage.service import StorageError

DATA = Path("/fixtures/docx/v1/client-intake-uk-v1.docx").read_bytes()
META = {"kind": "template", "filename": "Заява.docx", "title": "  Заява Ґанни  "}


@pytest.fixture(autouse=True)
def document_store(account_database, tmp_path, monkeypatch):
    initialize(tmp_path, os.getuid(), os.getgid())
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("STORAGE_DISK_HEADROOM_BYTES", "0")
    yield tmp_path
    with database().begin() as connection:
        for table in (versions, resources, audit_events, files, reservations):
            connection.execute(delete(table))


def client():
    result = browser()
    assert sign_in(result).status_code == 200
    return result


def upload(web, key="first", data=DATA, **metadata):
    return web.post(
        "/api/documents",
        content=data,
        headers={
            "Content-Type": routes.MIME,
            "Idempotency-Key": key,
            "X-Upload-Metadata": base64.b64encode(
                json.dumps({**META, **metadata}, ensure_ascii=False).encode()
            ).decode(),
        },
    )


def counts():
    with database().connect() as connection:
        return tuple(
            connection.execute(select(func.count()).select_from(table)).scalar_one()
            for table in (resources, versions, files, reservations)
        )


def test_uploads_keep_originals_and_initial_models_and_retries_charge_once(
    document_store,
):
    owner = account()
    web = client()
    first = upload(web)
    assert first.status_code == 201, first.text
    assert not first.request.url.query
    result = first.json()
    assert result["title"] == "Заява Ґанни"
    assert result["processing_status"] == "not_started"
    assert result["digest"] == hashlib.sha256(DATA).hexdigest()
    assert result["unsupported_count"] > 0
    assert first.headers["cache-control"] == "no-store"
    assert upload(web).json() == result
    assert counts() == (1, 1, 1, 1)
    with database().connect() as connection:
        row = connection.execute(select(resources)).mappings().one()
        version = connection.execute(select(versions)).mappings().one()
        charged = (
            connection.execute(select(accounts).where(accounts.c.user_id == owner.id))
            .mappings()
            .one()
        )
    original = document_store / "files" / str(owner.id) / str(row["original_file_id"])
    assert original.read_bytes() == DATA
    assert original.stat().st_mode & 0o222 == 0
    assert version["file_id"] == row["original_file_id"]
    assert (
        version["document_model"]
        == service.validate_upload(DATA, META["filename"]).model
    )
    assert version["number"] == 1
    assert (charged["used_bytes"], charged["reserved_bytes"]) == (len(DATA), 0)
    assert upload(web, title="different").status_code == 409
    assert counts() == (1, 1, 1, 1)
    one_off = upload(web, key="one-off", kind="document")
    assert one_off.status_code == 201
    assert one_off.json()["id"] != result["id"]
    assert original.read_bytes() == DATA
    # A new engine/client reads persisted metadata; no process-local resource cache.
    database().dispose()
    assert client().get("/api/documents/" + result["id"]).json() == result
    with pytest.raises(RuntimeError, match="Documents exist"):
        command.downgrade(Config("alembic.ini"), "0004_storage_audit")


def test_lists_and_metadata_reads_are_owned_paginated_and_validated():
    account()
    web = client()
    first = upload(web).json()
    second = upload(web, key="second").json()
    upload(web, key="doc", kind="document")
    page = web.get("/api/documents", params={"kind": "template", "limit": 1})
    assert page.status_code == 200 and page.headers["cache-control"] == "no-store"
    assert page.json()["items"][0]["id"] == second["id"]
    next_page = web.get(
        "/api/documents",
        params={"kind": "template", "limit": 1, "cursor": page.json()["next_cursor"]},
    ).json()
    assert next_page["items"][0]["id"] == first["id"]
    assert next_page["next_cursor"] is None
    assert (
        len(web.get("/api/documents", params={"kind": "document"}).json()["items"]) == 1
    )
    other = accounts_service.provision(
        AccountInput(email="other@example.test", display_name="Other"), PASSWORD
    )
    peer = browser()
    response = peer.post(
        "/api/auth/login", json={"email": other.email, "password": PASSWORD}
    )
    peer.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    assert peer.get("/api/documents/" + first["id"]).status_code == 404
    assert peer.get("/api/documents", params={"kind": "template"}).json()["items"] == []
    assert (
        peer.get(
            "/api/documents", params={"kind": "template", "cursor": first["id"]}
        ).status_code
        == 422
    )
    for params in (
        {"kind": "bad"},
        {"kind": "template", "limit": 101},
        {"kind": "template", "cursor": str(uuid4())},
    ):
        assert web.get("/api/documents", params=params).status_code == 422
    assert (
        browser().get("/api/documents", params={"kind": "template"}).status_code == 401
    )
    assert upload(peer).status_code == 201  # The same key is scoped to another owner.


def test_rejections_leave_no_resource_or_bytes_and_enforce_mutation_auth(
    document_store,
):
    owner = account()
    web = client()
    for data, metadata, code in (
        (b"invalid", {}, "invalid_document"),
        (DATA, {"filename": "x.docm"}, "unsupported_document"),
    ):
        result = upload(web, data=data, **metadata)
        assert result.status_code == 422 and result.json()["error"]["code"] == code
    for metadata in (
        {"title": " "},
        {"title": "invalid\x00title"},
        {"owner_id": str(uuid4())},
        {"kind": "bad"},
    ):
        assert upload(web, **metadata).status_code == 422
    assert upload(browser()).status_code == 401
    for headers in ({"Origin": "http://other.test"}, {"X-CSRF-Token": "wrong"}):
        response = web.post(
            "/api/documents",
            content=DATA,
            headers={
                "Content-Type": routes.MIME,
                "Idempotency-Key": "a",
                "X-Upload-Metadata": base64.b64encode(
                    json.dumps(META).encode()
                ).decode(),
                **headers,
            },
        )
        assert response.status_code == 403
    assert counts() == (0, 0, 0, 0)
    set_override(owner.id, 0)
    result = upload(web)
    assert (
        result.status_code == 409 and result.json()["error"]["code"] == "quota_exceeded"
    )
    assert counts() == (0, 0, 0, 0)
    assert not any(path.is_file() for path in (document_store / "files").rglob("*"))


def test_finalization_failure_rolls_back_resource_and_releases_bytes(
    document_store, monkeypatch
):
    owner = account()
    web = client()
    original = service.active_user
    calls = 0

    def revoke(connection, state):
        nonlocal calls
        calls += 1
        if calls == 2:
            connection.execute(delete(sessions).where(sessions.c.user_id == owner.id))
        return original(connection, state)

    monkeypatch.setattr(service, "active_user", revoke)
    result = upload(web)
    assert result.status_code == 401
    assert counts() == (0, 0, 1, 1)
    with database().connect() as connection:
        assert connection.execute(select(files.c.state)).scalar_one() == "deleted"
        assert connection.execute(
            select(accounts.c.used_bytes, accounts.c.reserved_bytes)
        ).one() == (0, 0)
    assert not list((document_store / "files" / str(owner.id)).iterdir())
    monkeypatch.setattr(service, "active_user", original)
    assert upload(web).json()["error"]["code"] == "operation_aborted"
    assert upload(web, key="retry-new").status_code == 201


def test_database_constraints_and_empty_downgrade_upgrade():
    account()
    first = upload(client()).json()
    with pytest.raises(IntegrityError):
        with database().begin() as connection:
            connection.execute(update(resources).values(owner_id=uuid4()))
    with pytest.raises(IntegrityError):
        with database().begin() as connection:
            connection.execute(update(resources).values(current_version_id=uuid4()))
    with database().begin() as connection:
        connection.execute(delete(versions))
        connection.execute(delete(resources))
    command.downgrade(Config("alembic.ini"), "0004_storage_audit")
    command.upgrade(Config("alembic.ini"), "head")
    assert client().get("/api/documents/" + first["id"]).status_code == 404


def test_request_admission_errors_and_slots_are_released(monkeypatch):
    account()
    web = client()
    routes.UPLOAD_SLOTS.acquire()
    routes.UPLOAD_SLOTS.acquire()
    try:
        assert upload(web).json()["error"]["code"] == "upload_busy"
    finally:
        routes.UPLOAD_SLOTS.release()
        routes.UPLOAD_SLOTS.release()
    for error, code in (
        (StorageError("disk_capacity"), "storage_unavailable"),
        (StorageError("operation_in_progress"), "operation_in_progress"),
        (StorageError("file_too_large"), "file_too_large"),
        (StorageError("invalid_request"), "invalid_request"),
        (SQLAlchemyError("private details"), "storage_unavailable"),
    ):

        def fail(*args):
            raise error

        monkeypatch.setattr(service, "upload", fail)
        assert upload(web).json()["error"]["code"] == code
    assert routes.UPLOAD_SLOTS.acquire(blocking=False)
    routes.UPLOAD_SLOTS.release()


def test_bounded_body_validates_actual_bytes_headers_and_timeout(monkeypatch):
    async def read(chunks, headers):
        iterator = iter(enumerate(chunks))

        async def receive():
            index, chunk = next(iterator)
            return {
                "type": "http.request",
                "body": chunk,
                "more_body": index < len(chunks) - 1,
            }

        request = Request(
            {
                "type": "http",
                "headers": [
                    (key.encode(), value.encode()) for key, value in headers.items()
                ],
            },
            receive,
        )
        return await routes.read_body(request)

    base = {"content-type": routes.MIME}
    assert asyncio.run(read([b"abc", b"def"], base)) == b"abcdef"
    with pytest.raises(AppError) as result:
        asyncio.run(read([b"short"], {**base, "content-length": "10"}))
    assert result.value.detail.code == "invalid_request"
    for headers, code in (
        ({}, "unsupported_document"),
        ({**base, "content-length": "bad"}, "invalid_request"),
        ({**base, "content-length": str(routes.ARCHIVE_BYTES + 1)}, "file_too_large"),
    ):
        with pytest.raises(AppError) as result:
            asyncio.run(read([], headers))
        assert result.value.detail.code == code
    with pytest.raises(AppError) as result:
        asyncio.run(read([b"x" * (routes.ARCHIVE_BYTES + 1)], base))
    assert result.value.detail.code == "file_too_large"

    async def delayed():
        async def receive():
            await asyncio.sleep(1)

        request = Request(
            {"type": "http", "headers": [(b"content-type", routes.MIME.encode())]},
            receive,
        )
        await routes.read_body(request)

    monkeypatch.setattr(routes, "BODY_SECONDS", 0.001)
    with pytest.raises(AppError) as result:
        asyncio.run(delayed())
    assert result.value.detail.code == "upload_timeout"


def test_concurrent_retry_cannot_see_partial_resource_or_duplicate_charge(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager
    from threading import Event

    from app.storage.filesystem import FileSystem

    owner = account()
    first, second = client(), client()
    entered, release = Event(), Event()
    stage = FileSystem.stage

    @contextmanager
    def paused(fs, operation):
        with stage(fs, operation) as stream:
            entered.set()
            assert release.wait(10)
            yield stream

    monkeypatch.setattr(FileSystem, "stage", paused)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(upload, first)
        try:
            assert entered.wait(10)
            assert (
                second.get("/api/documents", params={"kind": "template"}).json()[
                    "items"
                ]
                == []
            )
            retry = upload(second)
            assert retry.status_code == 409
            assert retry.json()["error"]["code"] == "operation_in_progress"
        finally:
            release.set()
        result = future.result(timeout=10)
    assert result.status_code == 201
    assert upload(second).json() == result.json()
    assert counts() == (1, 1, 1, 1)
    with database().connect() as connection:
        assert connection.execute(
            select(accounts.c.used_bytes, accounts.c.reserved_bytes).where(
                accounts.c.user_id == owner.id
            )
        ).one() == (len(DATA), 0)


def test_service_requires_identity_and_parser_limits_use_machine_codes(monkeypatch):
    from app.documents.package import InvalidDocument
    from app.documents.schema import UploadMetadata

    with pytest.raises(AppError) as result:
        service.upload(
            accounts_service.bootstrap(None), UploadMetadata(**META), DATA, "x"
        )
    assert result.value.status == 401
    account()
    web = client()

    def limited(*args):
        raise InvalidDocument("processing_limit")

    monkeypatch.setattr(service, "validate_upload", limited)
    assert upload(web).json()["error"]["code"] == "document_limit"
    assert counts() == (0, 0, 0, 0)
