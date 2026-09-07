import json
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from test_accounts import PASSWORD, account, browser
from test_accounts import account_database as account_database
from test_document_persistence import DATA, client, counts, upload
from test_document_persistence import document_store as document_store
from test_template_copies import amounts

from app.accounts import service as accounts_service
from app.accounts.schema import AccountInput
from app.documents import titles
from app.documents.schema import resources
from app.infrastructure import database
from app.storage.quotas import set_override
from app.storage.schema import files


def rename(web, saved, **changes):
    payload = {
        "source_version_id": saved["current_version_id"],
        "previous_title": saved["title"],
        "title": "Нова назва Ґанни",
        **changes,
    }
    return web.patch(
        f"/api/documents/{saved['id']}/title",
        content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )


@pytest.mark.parametrize("kind", ["template", "document"])
def test_rename_changes_only_owned_display_metadata_and_replays_exactly(kind):
    owner = account()
    web = client()
    saved = upload(web, kind=kind).json()
    before = web.get(f"/api/documents/{saved['id']}/content").json()["document"]
    set_override(owner.id, 0)
    response = rename(web, saved, title="  Нова назва Ґанни  ")
    assert response.status_code == 200
    result = response.json()
    assert result["title"] == "Нова назва Ґанни"
    for key in (
        "current_version_id",
        "original_filename",
        "digest",
        "size_bytes",
        "kind",
    ):
        assert result[key] == saved[key]
    assert response.headers["cache-control"] == "no-store"
    assert rename(web, saved).json() == result
    assert counts() == (1, 1, 1, 1)
    assert amounts(owner) == (len(DATA), 0)
    assert web.get(f"/api/documents/{saved['id']}/download").content == DATA
    assert web.get(f"/api/documents/{saved['id']}/content").json()["document"] == before
    assert (
        web.get(f"/api/documents?kind={kind}").json()["items"][0]["title"]
        == result["title"]
    )


def test_competing_renames_require_current_title_and_revision():
    account()
    web = client()
    saved = upload(web).json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(lambda title: rename(web, saved, title=title), ["Перша", "Друга"])
        )
    assert sorted(response.status_code for response in responses) == [200, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["error"]["parameters"] == {"reason": "title"}
    winner = next(
        response.json() for response in responses if response.status_code == 200
    )
    stale = rename(web, winner, source_version_id=str(uuid4()))
    assert stale.status_code == 409
    assert stale.json()["error"]["parameters"] == {"reason": "revision"}
    assert rename(web, saved, title=winner["title"]).json() == winner


def test_rename_requires_current_owner_session_and_csrf_and_rejects_deleted_resources():
    account()
    web = client()
    saved = upload(web).json()
    assert rename(browser(), saved).status_code == 401
    peer = accounts_service.provision(
        AccountInput(email="peer@example.test", display_name="Peer"), PASSWORD
    )
    other = browser()
    login = other.post(
        "/api/auth/login", json={"email": peer.email, "password": PASSWORD}
    )
    other.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert rename(other, saved).status_code == 404
    token = web.headers["X-CSRF-Token"]
    web.headers["X-CSRF-Token"] = "bad"
    assert rename(web, saved).status_code == 403
    web.headers["X-CSRF-Token"] = token
    assert web.delete(f"/api/documents/{saved['id']}").status_code == 200
    assert rename(web, saved).status_code == 404


@pytest.mark.parametrize("title", [" ", "🙂" * 161, "bad\nname", "\ud800"])
def test_invalid_titles_leave_resource_unchanged(title):
    account()
    web = client()
    saved = upload(web).json()
    assert rename(web, saved, title=title).status_code == 422
    assert web.get(f"/api/documents/{saved['id']}").json()["title"] == saved["title"]


def test_unavailable_resource_rolls_back_title_and_database_failures_are_private(
    monkeypatch,
):
    account()
    web = client()
    saved = upload(web).json()
    with database().begin() as connection:
        connection.execute(update(files).values(state="pending_delete"))
    assert rename(web, saved).status_code == 404
    with database().connect() as connection:
        assert (
            connection.execute(
                select(resources.c.title).where(resources.c.id == UUID(saved["id"]))
            ).scalar_one()
            == saved["title"]
        )

    def unavailable(*args):
        raise SQLAlchemyError("private metadata")

    monkeypatch.setattr(titles, "rename", unavailable)
    response = rename(web, saved)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "dependencies_unavailable"
    assert "private" not in response.text
    assert response.headers["cache-control"] == "no-store"
