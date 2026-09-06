from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event

import pytest
from sqlalchemy import select, update
from test_accounts import PASSWORD, account, browser, sign_in
from test_accounts import account_database as account_database

from app.accounts import profile, service
from app.accounts.schema import login_attempts, users
from app.errors import AppError
from app.infrastructure import database

NEW_PASSWORD = "New-synthetic-Ґанна-2026"


def signed_client():
    client = browser()
    assert sign_in(client).status_code == 200
    return client


def test_profile_renaming_is_validated_owner_only_and_persistent():
    owner = account()
    client = signed_client()
    result = client.patch("/api/profile", json={"display_name": "  Ґанна Їжак  "})
    assert result.status_code == 200
    assert result.json()["user"]["display_name"] == "Ґанна Їжак"
    assert result.json()["user"]["email"] == owner.email
    assert (
        "password_hash" not in result.text
        and result.headers["cache-control"] == "no-store"
    )
    assert (
        client.get("/api/auth/session").json()["user"]["display_name"] == "Ґанна Їжак"
    )
    for payload in (
        {"display_name": " "},
        {"display_name": "x" * 121},
        {"display_name": "valid", "role": "admin"},
        {"display_name": "valid", "quota_override_bytes": 0},
        {"display_name": "valid", "ui_language": "en"},
    ):
        assert client.patch("/api/profile", json=payload).status_code == 422
    assert (
        client.patch(
            "/api/profile",
            json={"display_name": "valid"},
            headers={"Origin": "http://other.test"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/api/profile",
            json={"display_name": "valid"},
            headers={"X-CSRF-Token": "wrong"},
        ).status_code
        == 403
    )
    anonymous = browser()
    assert (
        anonymous.patch("/api/profile", json={"display_name": "valid"}).status_code
        == 401
    )


def test_password_change_verifies_current_rotates_and_revokes_other_sessions():
    account()
    first, second = signed_client(), signed_client()
    old_csrf = first.headers["X-CSRF-Token"]
    old_cookie = first.cookies.get("fillable_session_v1")
    wrong = first.post(
        "/api/profile/password",
        json={"current_password": "wrong", "new_password": NEW_PASSWORD},
    )
    assert (
        wrong.status_code == 400
        and wrong.json()["error"]["code"] == "current_password_invalid"
    )
    assert first.get("/api/auth/session").json()["user"] is not None
    assert second.get("/api/auth/session").json()["user"] is not None
    for changes in (
        {"new_password": "short"},
        {"current_password": ""},
        {"role": "admin"},
    ):
        assert (
            first.post(
                "/api/profile/password",
                json={
                    "current_password": PASSWORD,
                    "new_password": NEW_PASSWORD,
                    **changes,
                },
            ).status_code
            == 422
        )
    result = first.post(
        "/api/profile/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert result.status_code == 200
    assert first.cookies.get("fillable_session_v1") != old_cookie
    assert result.json()["csrf_token"] != old_csrf
    assert second.get("/api/auth/session").json()["user"] is None
    assert sign_in(browser(), PASSWORD).status_code == 401
    assert sign_in(browser(), NEW_PASSWORD).status_code == 200
    assert (
        first.patch("/api/profile", json={"display_name": "valid"}).status_code == 403
    )
    first.headers["X-CSRF-Token"] = result.json()["csrf_token"]
    assert (
        first.patch("/api/profile", json={"display_name": "Оновлено"}).status_code
        == 200
    )


def test_current_password_failures_are_rate_limited_and_expire():
    owner = account()
    client = signed_client()
    payload = {"current_password": "wrong", "new_password": NEW_PASSWORD}
    for _ in range(5):
        assert client.post("/api/profile/password", json=payload).status_code == 400
    assert client.post("/api/profile/password", json=payload).status_code == 429
    key = service.attempt_key(f"password-change:{owner.id}")
    with database().begin() as connection:
        connection.execute(
            update(login_attempts)
            .where(login_attempts.c.key == key)
            .values(
                expires_at=service.now() - timedelta(seconds=1),
            )
        )
    payload["current_password"] = PASSWORD
    assert client.post("/api/profile/password", json=payload).status_code == 200
    anonymous = service.bootstrap(None)
    with pytest.raises(AppError):
        profile.change_password(anonymous, profile.PasswordInput(**payload))


def test_revoked_or_deactivated_sessions_cannot_mutate_after_initial_authentication():
    owner = account()
    client = signed_client()
    state = service.read_session(client.cookies.get("fillable_session_v1"))
    service.logout(state.token)
    with pytest.raises(AppError):
        profile.rename(state, profile.NameInput(display_name="stale"))
    client = signed_client()
    state = service.read_session(client.cookies.get("fillable_session_v1"))
    with database().begin() as connection:
        connection.execute(
            update(users).where(users.c.id == owner.id).values(active=False)
        )
    with pytest.raises(AppError):
        profile.change_password(
            state,
            profile.PasswordInput(current_password=PASSWORD, new_password=NEW_PASSWORD),
        )
    with database().connect() as connection:
        assert (
            connection.execute(
                select(users.c.display_name).where(users.c.id == owner.id)
            ).scalar_one()
            != "stale"
        )


def test_operator_reset_and_login_use_the_same_lock_order(monkeypatch):
    account()
    token = service.bootstrap(None).token
    locked, proceed = Event(), Event()
    lock_attempt = service.lock_attempt

    def paused(connection, key):
        result = lock_attempt(connection, key)
        if not locked.is_set():
            locked.set()
            assert proceed.wait(5)
        return result

    monkeypatch.setattr(service, "lock_attempt", paused)
    with ThreadPoolExecutor(2) as pool:
        reset = pool.submit(service.reset_password, "client@example.test", NEW_PASSWORD)
        assert locked.wait(5)
        login = pool.submit(service.login, token, "client@example.test", NEW_PASSWORD)
        proceed.set()
        reset.result(5)
        assert login.result(5).user is not None
