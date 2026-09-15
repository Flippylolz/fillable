from uuid import uuid4

import pytest
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from test_accounts import PASSWORD, account, browser
from test_accounts import account_database as account_database
from test_document_persistence import DATA, client, counts, upload
from test_document_persistence import document_store as document_store
from test_template_copies import amounts

from app.accounts import service as accounts_service
from app.accounts.schema import AccountInput
from app.documents import previews, routes
from app.documents.schema import resources
from app.infrastructure import database
from app.storage.quotas import set_override
from app.storage.service import StorageError


def mark(web, saved, version=None):
    return web.post(
        f"/api/documents/{saved['id']}/preview",
        json={"source_version_id": version or saved["current_version_id"]},
    )


def preview(web, saved, version=None):
    return web.get(
        f"/api/documents/{saved['id']}/preview",
        params={"source_version_id": version or saved["current_version_id"]},
    )


@pytest.mark.parametrize("kind", ["template", "document"])
def test_first_render_persists_owned_revision_preview_without_retained_writes(kind):
    owner = account()
    web = client()
    saved = upload(web, kind=kind).json()
    assert saved["preview_ready"] is False
    assert preview(web, saved).status_code == 404
    content = web.get(f"/api/documents/{saved['id']}/content").json()
    assert content["resource"]["preview_ready"] is False
    set_override(owner.id, 0)
    result = mark(web, saved)
    assert result.status_code == 200
    assert result.json()["preview_ready"] is True
    assert result.headers["cache-control"] == "no-store"
    assert mark(web, saved).json() == result.json()
    fresh = client()
    fetched = preview(fresh, saved)
    assert fetched.status_code == 200
    assert fetched.headers["cache-control"] == "no-store"
    assert fetched.json()["document"] == content["document"]
    assert fetched.json()["presentation"] == content["presentation"]
    assert (
        fresh.get(f"/api/documents?kind={kind}").json()["items"][0]["preview_ready"]
        is True
    )
    assert counts() == (1, 1, 1, 1)
    assert amounts(owner) == (len(DATA), 0)
    assert web.get(f"/api/documents/{saved['id']}/download").content == DATA


def test_stale_and_foreign_receipts_cannot_enable_or_read_previews():
    account()
    web = client()
    saved = upload(web).json()
    assert mark(web, saved, str(uuid4())).status_code == 409
    assert preview(web, saved).status_code == 404
    assert mark(browser(), saved).status_code == 401
    token = web.headers["X-CSRF-Token"]
    web.headers["X-CSRF-Token"] = "bad"
    assert mark(web, saved).status_code == 403
    web.headers["X-CSRF-Token"] = token
    assert mark(web, saved).status_code == 200
    assert preview(web, saved, str(uuid4())).status_code == 404
    peer = accounts_service.provision(
        AccountInput(email="peer@example.test", display_name="Peer"), PASSWORD
    )
    other = browser()
    login = other.post(
        "/api/auth/login", json={"email": peer.login, "password": PASSWORD}
    )
    other.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert mark(other, saved).status_code == 404
    assert preview(other, saved).status_code == 404
    with database().begin() as connection:
        connection.execute(
            update(resources)
            .where(resources.c.id == saved["id"])
            .values(state="deleted")
        )
    assert mark(web, saved).status_code == 404
    assert preview(web, saved).status_code == 404


@pytest.mark.parametrize("operation", ["mark_rendered", "preview"])
def test_preview_database_errors_are_safe(monkeypatch, operation):
    account()
    web = client()
    saved = upload(web).json()

    def fail(*args):
        raise SQLAlchemyError("private details")

    monkeypatch.setattr(previews, operation, fail)
    response = mark(web, saved) if operation == "mark_rendered" else preview(web, saved)
    assert response.status_code == 503
    assert "private details" not in response.text


@pytest.mark.parametrize(
    "code,status",
    [("not_found", 404), ("operation_in_progress", 409), ("storage_failure", 503)],
)
def test_preview_storage_errors_are_safe(monkeypatch, code, status):
    account()
    web = client()
    saved = upload(web).json()

    def fail(*args):
        raise StorageError(code)

    monkeypatch.setattr(previews, "preview", fail)
    assert preview(web, saved).status_code == status


def test_preview_honors_download_concurrency_bound():
    account()
    web = client()
    saved = upload(web).json()
    routes.DOWNLOAD_SLOTS.acquire()
    routes.DOWNLOAD_SLOTS.acquire()
    try:
        assert preview(web, saved).status_code == 409
    finally:
        routes.DOWNLOAD_SLOTS.release()
        routes.DOWNLOAD_SLOTS.release()


def test_saves_and_template_copies_start_with_their_own_unrendered_revision():
    from test_document_saves import save, start

    _, web, saved, payload = start("template")
    assert mark(web, saved).status_code == 200
    current = save(web, saved, payload).json()["resource"]
    assert current["preview_ready"] is False
    assert preview(web, current).status_code == 404
    assert mark(web, saved).status_code == 409
    assert mark(web, current).status_code == 200
    assert (
        preview(web, current).json()["document"]
        == web.get(f"/api/documents/{saved['id']}/content").json()["document"]
    )
    copied = web.post(
        f"/api/documents/{current['id']}/copies",
        json={
            "source_version_id": current["current_version_id"],
            "title": "Preview copy",
        },
        headers={"idempotency-key": "preview-copy"},
    )
    assert copied.status_code == 201
    assert copied.json()["preview_ready"] is False
    assert preview(web, copied.json()).status_code == 404
    assert mark(web, copied.json()).status_code == 200
    assert preview(web, copied.json()).status_code == 200
