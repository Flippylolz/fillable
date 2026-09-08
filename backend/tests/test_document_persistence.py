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
from app.documents.lease_schema import leases
from app.documents.schema import resources, versions
from app.errors import AppError
from app.infrastructure import database
from app.jobs.schema import jobs
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
        for table in (
            leases,
            jobs,
            versions,
            resources,
            audit_events,
            files,
            reservations,
        ):
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
    assert result["processing_status"] == "queued"
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
    with database().begin() as connection:
        connection.execute(delete(jobs))
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
        "/api/auth/login", json={"email": other.login, "password": PASSWORD}
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
        connection.execute(delete(jobs))
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


def test_download_is_exact_saved_docx_owned_and_not_a_new_allocation():
    from urllib.parse import quote

    account()
    web = client()
    for kind in ("template", "document"):
        saved = upload(web, key=kind, kind=kind, filename='Заява "Їжак".docx').json()
        before = counts()
        url = "/api/documents/" + saved["id"] + "/download"
        result = web.get(url)
        assert result.status_code == 200 and result.content == DATA
        assert result.headers["content-type"] == routes.MIME
        assert result.headers["cache-control"] == "no-store"
        assert result.headers["x-content-type-options"] == "nosniff"
        assert result.headers["x-fillable-version"] == saved["current_version_id"]
        assert (
            quote(saved["original_filename"], safe="")
            in result.headers["content-disposition"]
        )
        assert web.get(url).content == DATA and counts() == before
        assert browser().get(url).status_code == 401
    other = accounts_service.provision(
        AccountInput(email="other@example.test", display_name="Other"), PASSWORD
    )
    peer = browser()
    peer.post("/api/auth/login", json={"email": other.login, "password": PASSWORD})
    assert peer.get(url).status_code == 404
    assert web.get(f"/api/documents/{uuid4()}/download").status_code == 404
    with database().begin() as connection:
        connection.execute(update(resources).values(state="deleted"))
    assert web.get(url).status_code == 404
    web.post("/api/auth/logout")
    assert web.get(url).status_code == 401


def test_download_corruption_and_admission_never_return_partial_success(
    document_store,
    monkeypatch,
):
    owner = account()
    web = client()
    saved = upload(web).json()
    url = "/api/documents/" + saved["id"] + "/download"
    with database().connect() as connection:
        file = connection.execute(select(files)).mappings().one()
    path = document_store / "files" / str(owner.id) / str(file["id"])
    path.chmod(0o600)
    path.write_bytes(b"corrupt")
    result = web.get(url)
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "storage_unavailable"
    assert "content-disposition" not in result.headers
    path.unlink()
    assert web.get(url).status_code == 503
    routes.DOWNLOAD_SLOTS.acquire()
    routes.DOWNLOAD_SLOTS.acquire()
    try:
        assert web.get(url).json()["error"]["code"] == "operation_in_progress"
    finally:
        routes.DOWNLOAD_SLOTS.release()
        routes.DOWNLOAD_SLOTS.release()
    for error, status in (
        (StorageError("not_found"), 404),
        (StorageError("operation_in_progress"), 409),
        (SQLAlchemyError("private path and document text"), 503),
    ):

        def fail(*args):
            raise error

        monkeypatch.setattr(service, "download", fail)
        result = web.get(url)
        assert result.status_code == status
        assert "private" not in result.text
        assert result.headers["cache-control"] == "no-store"
    assert routes.DOWNLOAD_SLOTS.acquire(blocking=False)
    routes.DOWNLOAD_SLOTS.release()


def test_download_follows_current_revision_and_preserves_original_bytes():
    from sqlalchemy import insert

    from app.storage.configuration import configured

    owner = account()
    web = client()
    saved = upload(web).json()
    identity = uuid4()  # A retained second revision has a distinct identity/file.
    content = DATA + b"synthetic saved revision marker"
    with database().connect() as connection:
        resource = connection.execute(select(resources)).mappings().one()
        initial = connection.execute(select(versions)).mappings().one()

    def finalize(connection, result):
        connection.execute(
            insert(versions).values(
                id=identity,
                document_id=resource["id"],
                owner_id=owner.id,
                file_id=result.id,
                number=2,
                document_model=initial["document_model"],
                unsupported_count=initial["unsupported_count"],
            )
        )
        connection.execute(
            update(resources)
            .where(resources.c.id == resource["id"])
            .values(current_version_id=identity)
        )

    store = configured()
    store.store(
        owner.id,
        "saved-revision",
        hashlib.sha256(content).hexdigest(),
        "version",
        [content],
        expected_bytes=len(content),
        finalize=finalize,
    )
    result = web.get("/api/documents/" + saved["id"] + "/download")
    assert result.content == content
    assert result.headers["x-fillable-version"] == str(identity)
    with store.read(owner.id, resource["original_file_id"]) as original:
        assert original.read() == DATA


def test_workspace_content_is_a_single_owned_verified_revision(
    document_store, monkeypatch
):
    owner = account()
    web = client()
    saved = upload(web).json()
    url = "/api/documents/" + saved["id"] + "/content"
    result = web.get(url)
    assert result.status_code == 200
    assert result.json()["resource"] == saved
    with database().connect() as connection:
        version = connection.execute(select(versions)).mappings().one()
    assert result.json()["document"] == version["document_model"]
    assert result.headers["cache-control"] == "no-store"
    assert browser().get(url).status_code == 401
    assert web.get(f"/api/documents/{uuid4()}/content").status_code == 404
    other = accounts_service.provision(
        AccountInput(email="other@example.test", display_name="Other"), PASSWORD
    )
    peer = browser()
    peer.post("/api/auth/login", json={"email": other.login, "password": PASSWORD})
    assert peer.get(url).status_code == 404
    path = document_store / "files" / str(owner.id) / str(version["file_id"])
    path.chmod(0o600)
    path.write_bytes(b"corrupt")
    assert web.get(url).status_code == 503
    routes.DOWNLOAD_SLOTS.acquire()
    routes.DOWNLOAD_SLOTS.acquire()
    try:
        assert web.get(url).status_code == 409
    finally:
        routes.DOWNLOAD_SLOTS.release()
        routes.DOWNLOAD_SLOTS.release()
    for failure, status in (
        (StorageError("not_found"), 404),
        (StorageError("operation_in_progress"), 409),
        (SQLAlchemyError("private text"), 503),
    ):

        def fail(*args):
            raise failure

        monkeypatch.setattr(service, "content", fail)
        response = web.get(url)
        assert response.status_code == status and "private text" not in response.text


def test_upload_job_intent_rolls_back_with_file_and_quota(document_store, monkeypatch):
    owner = account()
    web = client()
    original = service.intent

    def fail(*args):
        original(*args)
        raise SQLAlchemyError("synthetic transaction interruption")

    monkeypatch.setattr(service, "intent", fail)
    assert upload(web).status_code == 503
    assert counts() == (0, 0, 1, 1)
    assert not list((document_store / "files" / str(owner.id)).iterdir())
    with database().connect() as connection:
        assert connection.execute(select(jobs)).first() is None
        assert connection.execute(select(files.c.state)).scalar_one() == "deleted"
        usage = (
            connection.execute(select(accounts).where(accounts.c.user_id == owner.id))
            .mappings()
            .one()
        )
        assert usage["used_bytes"] == 0 and usage["reserved_bytes"] == 0
