from sqlalchemy import select
from test_accounts import PASSWORD, account, browser, sign_in
from test_accounts import account_database as account_database

from app.accounts import service
from app.accounts.schema import AccountInput, users
from app.infrastructure import database
from app.storage.schema import accounts as storage_accounts


def test_language_is_owner_only_persistent_and_does_not_change_other_state():
    owner = account()
    other = service.provision(
        AccountInput(email="other@example.test", display_name="Other"), PASSWORD
    )
    client = browser()
    assert sign_in(client).status_code == 200
    with database().connect() as connection:
        before = connection.execute(select(users)).mappings().all()
        storage_before = connection.execute(select(storage_accounts)).mappings().all()
    for language in ("en", "uk", "en"):
        result = client.patch("/api/profile/language", json={"ui_language": language})
        assert result.status_code == 200
        assert result.headers["cache-control"] == "no-store"
        assert result.json()["user"]["ui_language"] == language
        assert client.get("/api/auth/session").json()["user"]["ui_language"] == language
    peer = browser()
    assert sign_in(peer).json()["user"]["ui_language"] == "en"
    with database().connect() as connection:
        after = connection.execute(select(users)).mappings().all()
        assert (
            connection.execute(select(storage_accounts)).mappings().all()
            == storage_before
        )
    expected = [
        {**row, "ui_language": "en"} if row["id"] == owner.id else dict(row)
        for row in before
    ]
    assert sorted(after, key=lambda row: str(row["id"])) == sorted(
        expected, key=lambda row: str(row["id"])
    )
    assert next(row for row in after if row["id"] == other.id)["ui_language"] == "uk"


def test_language_rejects_invalid_values_extra_fields_and_invalid_sessions():
    account()
    client = browser()
    sign_in(client)
    for value in ("ua", "EN", "", None, 1, ["en"]):
        assert (
            client.patch(
                "/api/profile/language", json={"ui_language": value}
            ).status_code
            == 422
        )
    for extra in (
        {"role": "admin"},
        {"user_id": "other"},
        {"display_name": "changed"},
        {"quota_override_bytes": 0},
    ):
        assert (
            client.patch(
                "/api/profile/language", json={"ui_language": "en", **extra}
            ).status_code
            == 422
        )
    for headers in ({"Origin": "http://other.test"}, {"X-CSRF-Token": "wrong"}):
        assert (
            client.patch(
                "/api/profile/language", json={"ui_language": "en"}, headers=headers
            ).status_code
            == 403
        )
    assert client.get("/api/auth/session").json()["user"]["ui_language"] == "uk"
    anonymous = browser()
    assert (
        anonymous.patch("/api/profile/language", json={"ui_language": "en"}).status_code
        == 401
    )
    assert client.post("/api/auth/logout").status_code == 200
    assert client.patch(
        "/api/profile/language", json={"ui_language": "en"}
    ).status_code in (401, 403)
