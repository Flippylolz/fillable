from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from test_accounts import PASSWORD, account, browser
from test_accounts import account_database as account_database
from test_document_persistence import DATA, client, counts, upload
from test_document_persistence import document_store as document_store
from test_template_copies import amounts

from app.accounts import service as accounts_service
from app.accounts.schema import AccountInput, sessions
from app.documents import leases as service
from app.documents.lease_schema import LeaseRequest, leases
from app.documents.schema import resources, versions
from app.errors import AppError
from app.infrastructure import database
from app.storage.quotas import set_override
from app.storage.schema import files


def request(web, saved, tab, action="acquire", generation=None, **changes):
    return web.post(
        f"/api/documents/{saved['id']}/editing-lease",
        json=dict(
            action=action,
            client_id=str(tab),
            source_version_id=saved["current_version_id"],
            lease_id=generation,
            **changes,
        ),
    )


def expire(**values):
    with database().begin() as connection:
        connection.execute(update(leases).values(**values))


@pytest.mark.parametrize("kind", ["template", "document"])
def test_same_tab_retry_renew_release_preserve_bytes_revision_and_quota(kind):
    owner = account()
    web = client()
    saved = upload(web, kind=kind).json()
    before = web.get(f"/api/documents/{saved['id']}/content").json()
    set_override(owner.id, 0)
    tab = uuid4()
    first = request(web, saved, tab)
    assert first.status_code == 200
    lease = first.json()
    assert lease["status"] == "active" and lease["valid_for_seconds"] == 60
    assert lease["source_version_id"] == saved["current_version_id"]
    assert first.headers["cache-control"] == "no-store"
    assert "session" not in first.text and "client_id" not in first.text
    retry = request(web, saved, tab).json()
    assert retry["lease_id"] == lease["lease_id"]
    assert retry["expires_at"] >= lease["expires_at"]
    renewed = request(web, saved, tab, "renew", lease["lease_id"])
    assert (
        renewed.status_code == 200 and renewed.json()["lease_id"] == lease["lease_id"]
    )
    assert counts() == (1, 1, 1, 1) and amounts(owner) == (len(DATA), 0)
    assert web.get(f"/api/documents/{saved['id']}/download").content == DATA
    assert web.get(f"/api/documents/{saved['id']}/content").json() == before
    for _ in range(2):
        released = request(web, saved, tab, "release", lease["lease_id"])
        assert released.status_code == 200 and released.json()["expires_at"] is None
        assert released.json()["valid_for_seconds"] == 0
    new = request(web, saved, tab).json()
    assert new["lease_id"] != lease["lease_id"]
    assert request(web, saved, tab, "renew", lease["lease_id"]).status_code == 409
    request(web, saved, tab, "release", lease["lease_id"])
    assert request(web, saved, tab, "renew", new["lease_id"]).status_code == 200


def test_two_tabs_race_for_one_holder_and_expired_renew_cannot_resurrect():
    account()
    web = client()
    saved = upload(web).json()
    tabs = [uuid4(), uuid4()]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda tab: request(web, saved, tab), tabs))
    assert sorted(item.status_code for item in responses) == [200, 409]
    winner = next(
        index for index, item in enumerate(responses) if item.status_code == 200
    )
    held = responses[winner].json()
    assert responses[1 - winner].json()["error"]["parameters"] == {
        "reason": "lease_busy"
    }
    wrong = request(web, saved, tabs[1 - winner], "renew", held["lease_id"])
    assert wrong.status_code == 409 and wrong.json()["error"]["parameters"] == {
        "reason": "lease_lost"
    }
    expire(expires_at=accounts_service.now() - timedelta(seconds=1))
    assert (
        request(web, saved, tabs[winner], "renew", held["lease_id"]).status_code == 409
    )
    successor = request(web, saved, tabs[1 - winner]).json()
    assert successor["lease_id"] != held["lease_id"]
    request(web, saved, tabs[winner], "release", held["lease_id"])
    assert (
        request(
            web, saved, tabs[1 - winner], "renew", successor["lease_id"]
        ).status_code
        == 200
    )


def test_sessions_fence_tab_identity_and_revocation_releases_holder():
    account()
    first, second = client(), client()
    saved = upload(first).json()
    tab = uuid4()
    held = request(first, saved, tab).json()
    assert request(second, saved, tab).status_code == 409
    assert request(second, saved, tab, "renew", held["lease_id"]).status_code == 409
    request(second, saved, tab, "release", held["lease_id"])
    assert request(first, saved, tab, "renew", held["lease_id"]).status_code == 200
    logout = first.post("/api/auth/logout")
    assert logout.status_code == 200
    first.headers["X-CSRF-Token"] = logout.json()["csrf_token"]
    replacement = request(second, saved, tab)
    assert (
        replacement.status_code == 200
        and replacement.json()["lease_id"] != held["lease_id"]
    )
    assert request(first, saved, tab, "renew", held["lease_id"]).status_code == 401


@pytest.mark.parametrize("column", ["expires_at", "last_seen_at"])
def test_holder_with_expired_authentication_does_not_block_a_live_session(column):
    account()
    first, second = client(), client()
    saved = upload(first).json()
    held = request(first, saved, uuid4()).json()
    with database().begin() as connection:
        session_hash = connection.execute(select(leases.c.session_hash)).scalar_one()
        connection.execute(
            update(sessions)
            .where(sessions.c.token_hash == session_hash)
            .values(**{column: accounts_service.now() - timedelta(days=1)})
        )
    replacement = request(second, saved, uuid4())
    assert (
        replacement.status_code == 200
        and replacement.json()["lease_id"] != held["lease_id"]
    )


def test_current_revision_is_required_and_old_release_cannot_affect_other_holder():
    account()
    web = client()
    saved = upload(web).json()
    tab = uuid4()
    held = request(web, saved, tab).json()
    stale = {**saved, "current_version_id": str(uuid4())}
    for action, generation in (("acquire", None), ("renew", held["lease_id"])):
        response = request(web, stale, tab, action, generation)
        assert response.status_code == 409 and response.json()["error"][
            "parameters"
        ] == {"reason": "revision"}
    assert request(web, stale, tab, "release", held["lease_id"]).status_code == 200
    assert request(web, saved, tab, "renew", held["lease_id"]).status_code == 200
    # A newly committed revision cannot inherit the old generation by acquisition.
    with database().begin() as connection:
        version = dict(connection.execute(select(versions)).mappings().one())
        version.update(id=uuid4(), number=2)
        connection.execute(insert(versions).values(**version))
        connection.execute(update(resources).values(current_version_id=version["id"]))
    current = {**saved, "current_version_id": str(version["id"])}
    assert request(web, saved, tab, "renew", held["lease_id"]).status_code == 409
    latest = request(web, current, tab).json()
    assert latest["lease_id"] != held["lease_id"]
    request(web, saved, tab, "release", held["lease_id"])
    assert request(web, current, tab, "renew", latest["lease_id"]).status_code == 200


def test_owner_session_csrf_and_resource_readiness_are_required():
    account()
    web = client()
    saved = upload(web).json()
    tab = uuid4()
    assert request(browser(), saved, tab).status_code == 401
    other_owner = accounts_service.provision(
        AccountInput(email="other@example.test", display_name="Other"), PASSWORD
    )
    other = browser()
    login = other.post(
        "/api/auth/login", json={"email": other_owner.login, "password": PASSWORD}
    )
    other.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert request(other, saved, tab).status_code == 404
    token = web.headers["X-CSRF-Token"]
    web.headers["X-CSRF-Token"] = "bad"
    assert request(web, saved, tab).status_code == 403
    web.headers["X-CSRF-Token"] = token
    with database().begin() as connection:
        connection.execute(update(files).values(state="pending_delete"))
    assert request(web, saved, tab).status_code == 404
    with database().begin() as connection:
        connection.execute(update(files).values(state="ready"))
    assert request(web, saved, tab).status_code == 200
    assert web.delete(f"/api/documents/{saved['id']}").status_code == 200
    assert request(web, saved, tab).status_code == 404
    with database().connect() as connection:
        assert connection.execute(select(leases)).first() is None


def test_invalid_generation_contract_database_errors_and_rechecked_session(monkeypatch):
    account()
    web = client()
    saved = upload(web).json()
    tab = uuid4()
    for action, generation in (
        ("renew", None),
        ("release", None),
        ("acquire", str(uuid4())),
    ):
        assert request(web, saved, tab, action, generation).status_code == 422
    state = accounts_service.SessionState("invalid", None, accounts_service.now())
    with pytest.raises(AppError) as rejected:
        service.change(
            state,
            UUID(saved["id"]),
            LeaseRequest(
                action="acquire",
                source_version_id=saved["current_version_id"],
                client_id=tab,
            ),
        )
    assert rejected.value.status == 401

    def unavailable(*args):
        raise SQLAlchemyError("private session")

    monkeypatch.setattr(service, "change", unavailable)
    response = request(web, saved, tab)
    assert (
        response.status_code == 503
        and response.json()["error"]["code"] == "dependencies_unavailable"
    )
    assert (
        "private" not in response.text
        and response.headers["cache-control"] == "no-store"
    )


def test_migration_owner_version_constraints_and_populated_downgrade_guard():
    account()
    web = client()
    saved = upload(web).json()
    tab = uuid4()
    held = request(web, saved, tab).json()
    with pytest.raises(RuntimeError, match="Editing leases exist"):
        command.downgrade(Config("alembic.ini"), "0007_field_results")
    for key in ("owner_id", "source_version_id", "document_id"):
        with pytest.raises(IntegrityError), database().begin() as connection:
            connection.execute(update(leases).values(**{key: uuid4()}))
    request(web, saved, tab, "release", held["lease_id"])
    config = Config("alembic.ini")
    command.downgrade(config, "0007_field_results")
    command.upgrade(config, "head")
    with database().connect() as connection:
        assert connection.execute(select(leases)).first() is None
        assert connection.execute(
            select(resources.c.current_version_id)
        ).scalar_one() == UUID(saved["current_version_id"])
        assert connection.execute(select(versions.c.document_model)).scalar_one()
    assert request(web, saved, tab).status_code == 200
