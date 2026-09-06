import io
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

import pytest
from alembic import command
from alembic.config import Config
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from app.accounts import cli, routes, service
from app.accounts.schema import AccountInput, login_attempts, sessions, users
from app.errors import AppError, register_errors
from app.infrastructure import database
from app.main import app

PASSWORD = "Synthetic-їжак-2026"


@pytest.fixture(autouse=True)
def account_database():
    command.upgrade(Config("alembic.ini"), "head")
    with database().begin() as connection:
        connection.execute(delete(sessions))
        connection.execute(delete(login_attempts))
        connection.execute(delete(users))
    yield
    with database().begin() as connection:
        connection.execute(delete(sessions))
        connection.execute(delete(login_attempts))
        connection.execute(delete(users))


def account(role="user", language="uk"):
    return service.provision(
        AccountInput(
            email="client@example.test",
            display_name="Ґанна Їжак",
            role=role,
            ui_language=language,
        ),
        PASSWORD,
    )


def browser():
    client = TestClient(app)
    response = client.get("/api/auth/session")
    assert response.status_code == 200
    client.headers.update(
        {"Origin": "http://testserver", "X-CSRF-Token": response.json()["csrf_token"]}
    )
    return client


def sign_in(client, password=PASSWORD):
    response = client.post(
        "/api/auth/login", json={"email": " CLIENT@example.test ", "password": password}
    )
    if response.status_code == 200:
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response


def test_login_rotates_session_restores_language_and_logout_revokes():
    user = account(language="en")
    client = browser()
    old = client.cookies.get(routes.COOKIE)
    response = sign_in(client)
    assert response.json()["user"]["id"] == str(user.id)
    assert response.json()["user"]["ui_language"] == "en"
    assert response.json()["user"]["display_name"] == "Ґанна Їжак"
    token = client.cookies.get(routes.COOKIE)
    assert token != old
    assert service.read_session(old) is None
    cookie = response.headers["set-cookie"]
    assert (
        "HttpOnly" in cookie
        and "SameSite=strict" in cookie
        and "Secure" not in cookie
        and "Domain" not in cookie
    )
    assert response.headers["cache-control"] == "no-store"
    assert "password_hash" not in response.text and token not in response.text
    assert client.get("/api/auth/session").json()["user"]["id"] == str(user.id)
    with database().connect() as connection:
        stored = connection.execute(select(users.c.password_hash)).scalar_one()
        assert stored != PASSWORD and stored.startswith("$argon2id$")
        assert connection.execute(
            select(sessions.c.token_hash)
        ).scalar_one() == service.token_hash(token)
    assert client.post("/api/auth/logout").json()["user"] is None
    assert service.read_session(token) is None
    assert client.cookies.get(routes.COOKIE) != token


def test_credentials_are_generic_and_throttled_even_for_unknown_users():
    client = browser()
    for _ in range(5):
        response = sign_in(client, "incorrect")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_credentials"
    assert sign_in(client).status_code == 429
    account()
    assert sign_in(client).status_code == 429
    with database().begin() as connection:
        connection.execute(
            update(login_attempts).values(
                expires_at=service.now() - timedelta(seconds=1)
            )
        )
    assert sign_in(client).status_code == 200
    with database().connect() as connection:
        assert (
            connection.execute(
                select(func.count()).select_from(login_attempts)
            ).scalar_one()
            == 0
        )


def test_origin_csrf_cookie_and_authorization_boundaries():
    account()
    client = browser()
    csrf = client.headers["x-csrf-token"]
    for headers in (
        {"Origin": "http://testserver:8180"},
        {"Origin": "https://testserver"},
        {"Origin": ""},
        {"X-CSRF-Token": ""},
        {"X-CSRF-Token": "wrong"},
    ):
        assert (
            client.post(
                "/api/auth/login",
                headers=headers,
                json={"email": "client@example.test", "password": PASSWORD},
            ).status_code
            == 403
        )
    assert (
        client.get(
            "/api/auth/session", headers={"Sec-Fetch-Site": "cross-site"}
        ).status_code
        == 403
    )
    assert sign_in(client).status_code == 200
    assert (
        client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf}).status_code
        == 403
    )
    protected = FastAPI()
    register_errors(protected)

    @protected.get("/user")
    def user_view(user=Depends(routes.current_user)):
        return user

    @protected.get("/admin")
    def admin_view(user=Depends(routes.administrator)):
        return user

    visitor = TestClient(protected)
    assert visitor.get("/user").status_code == 401
    visitor.cookies.update(client.cookies)
    assert visitor.get("/user").status_code == 200
    assert visitor.get("/admin").status_code == 403
    with database().begin() as connection:
        connection.execute(update(users).values(role="admin"))
    assert visitor.get("/admin").status_code == 200
    assert (
        visitor.get(
            "/user",
            headers={"Cookie": f"{routes.COOKIE}=invalid; {routes.COOKIE}=other"},
        ).status_code
        == 401
    )
    anonymous = browser()
    visitor.cookies.clear()
    visitor.cookies.update(anonymous.cookies)
    assert visitor.get("/user").status_code == 401
    assert (
        TestClient(app)
        .post("/api/auth/logout", headers={"Origin": "http://testserver"})
        .status_code
        == 401
    )


def test_expiry_idle_disable_and_reset_invalidate_sessions():
    account()
    client = browser()
    assert sign_in(client).status_code == 200
    with database().begin() as connection:
        connection.execute(
            update(sessions).values(last_seen_at=service.now() - timedelta(minutes=31))
        )
    assert client.get("/api/auth/session").json()["user"] is None
    client.headers["X-CSRF-Token"] = client.get("/api/auth/session").json()[
        "csrf_token"
    ]
    assert sign_in(client).status_code == 200
    with database().begin() as connection:
        connection.execute(
            update(sessions).values(expires_at=service.now() - timedelta(seconds=1))
        )
    assert client.get("/api/auth/session").json()["user"] is None
    client.headers["X-CSRF-Token"] = client.get("/api/auth/session").json()[
        "csrf_token"
    ]
    assert sign_in(client).status_code == 200
    service.reset_password("client@example.test", PASSWORD + "-new")
    assert client.get("/api/auth/session").json()["user"] is None
    client.headers["X-CSRF-Token"] = client.get("/api/auth/session").json()[
        "csrf_token"
    ]
    assert sign_in(client).status_code == 401
    assert sign_in(client, PASSWORD + "-new").status_code == 200
    with database().begin() as connection:
        connection.execute(update(users).values(active=False))
    assert client.get("/api/auth/session").json()["user"] is None
    client.headers["X-CSRF-Token"] = client.get("/api/auth/session").json()[
        "csrf_token"
    ]
    assert sign_in(client, PASSWORD + "-new").status_code == 401


def test_concurrent_attempts_commit_and_cannot_bypass_limit():
    with database().begin() as connection:
        token = service.issue(connection, None).token

    def attempt(_):
        try:
            service.login(token, "unknown@example.test", "incorrect")
        except AppError as error:
            return error.status

    with patch.object(service, "verify_password", return_value=False):
        with ThreadPoolExecutor(max_workers=8) as workers:
            statuses = list(workers.map(attempt, range(8)))
    assert statuses.count(401) == 5 and statuses.count(429) == 3
    with database().connect() as connection:
        assert connection.execute(select(login_attempts.c.count)).scalar_one() == 5


def test_provision_validation_duplicates_constraints_and_rehash():
    user = account()
    with pytest.raises(AppError) as duplicate:
        account()
    assert duplicate.value.detail.code == "account_exists"
    for password in ("short", "x" * 1025):
        with pytest.raises(ValueError):
            service.reset_password(user.email, password)
    with pytest.raises(AppError):
        service.reset_password("missing@example.test", PASSWORD)
    for changes in ({"role": "owner"}, {"ui_language": "xx"}):
        with pytest.raises(IntegrityError):
            with database().begin() as connection:
                connection.execute(update(users).values(**changes))
    with pytest.raises(ValueError):
        AccountInput(email=user.email, display_name=" ")
    with database().begin() as connection:
        connection.execute(
            update(users).values(
                password_hash=service.PasswordHasher(
                    memory_cost=8192, time_cost=1
                ).hash(PASSWORD)
            )
        )
    client = browser()
    assert sign_in(client).status_code == 200
    with database().connect() as connection:
        upgraded = connection.execute(select(users.c.password_hash)).scalar_one()
    assert not service.PASSWORDS.check_needs_rehash(upgraded)
    assert not service.verify_password("invalid-hash", PASSWORD)
    assert service.read_session(secrets.token_hex(32)) is None
    assert service.read_session("invalid") is None
    with pytest.raises(AppError) as expired:
        service.login(secrets.token_hex(32), user.email, PASSWORD)
    assert expired.value.status == 403
    assert service.require_role(user, "user") == user


def test_private_operator_commands_never_print_credentials():
    args = [
        "command",
        "provision",
        "--email",
        "operator@example.test",
        "--display-name",
        "Оператор",
        "--role",
        "admin",
        "--password-stdin",
    ]
    output = io.StringIO()
    with (
        patch("sys.argv", args),
        patch("sys.stdin", io.StringIO(PASSWORD + "\n")),
        patch("sys.stdout", output),
    ):
        assert cli.main() == 0
    assert PASSWORD not in output.getvalue()
    with (
        patch(
            "sys.argv",
            ["command", "reset-password", "--email", "operator@example.test"],
        ),
        patch("getpass.getpass", side_effect=[PASSWORD + "new", PASSWORD + "new"]),
    ):
        assert cli.main() == 0
    with (
        patch(
            "sys.argv",
            ["command", "reset-password", "--email", "operator@example.test"],
        ),
        patch("getpass.getpass", side_effect=["one", "two"]),
    ):
        assert cli.main() == 1
    with patch("sys.argv", args), patch("sys.stdin", io.StringIO(PASSWORD)):
        assert cli.main() == 1


def test_https_cookie_and_origin_configuration(monkeypatch):
    for value in (
        "ftp://example.test",
        "http://user@example.test",
        "http://example.test/path",
        "http://example.test?x=1",
        "http://example.test#fragment",
        "http://",
    ):
        monkeypatch.setenv("FILLABLE_PUBLIC_ORIGIN", value)
        with pytest.raises(ValueError):
            routes.public_origin()
    monkeypatch.setenv("FILLABLE_PUBLIC_ORIGIN", "https://example.test:443/")
    assert routes.public_origin() == "https://example.test"
    response = TestClient(app, base_url="https://example.test").get("/api/auth/session")
    assert "Secure" in response.headers["set-cookie"]
    monkeypatch.setenv("FILLABLE_PUBLIC_ORIGIN", "http://[::1]:8180")
    assert routes.public_origin() == "http://[::1]:8180"


def test_invalid_account_email_type_is_rejected():
    with pytest.raises(ValueError):
        AccountInput.model_validate({"email": 123, "display_name": "Ірина"})
