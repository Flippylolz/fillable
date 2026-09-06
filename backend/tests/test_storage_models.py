from datetime import timedelta
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError

from app.accounts.schema import AccountInput, users
from app.accounts.service import now, provision
from app.infrastructure import database
from app.storage.schema import (
    DEFAULT_LIMIT_BYTES,
    MAX_BYTES,
    QuotaAmounts,
    accounts,
    calculate_usage,
    files,
    reservations,
    settings,
)


@pytest.fixture(autouse=True)
def storage_database():
    command.upgrade(Config("alembic.ini"), "head")
    yield
    with database().begin() as connection:
        connection.execute(delete(files))
        connection.execute(delete(reservations))
        connection.execute(delete(accounts))
        connection.execute(delete(users))
        connection.execute(
            update(settings).values(default_limit_bytes=DEFAULT_LIMIT_BYTES, revision=0)
        )


def user(email="owner@example.test"):
    return provision(
        AccountInput(email=email, display_name="Ірина"), "Synthetic-їжак-2026"
    )


def operation(owner, **changes):
    return dict(
        id=uuid4(),
        owner_id=owner.id,
        file_id=uuid4(),
        idempotency_key="retry-key",
        request_fingerprint="a" * 64,
        purpose="original",
        lease_token=uuid4(),
        lease_expires_at=now() + timedelta(seconds=30),
        **changes,
    )


def stored(op, **changes):
    return {
        **dict(
            id=op["file_id"],
            owner_id=op["owner_id"],
            reservation_id=op["id"],
            size_bytes=4,
            digest="b" * 64,
        ),
        **changes,
    }


def test_new_accounts_inherit_default_and_usage_is_exact():
    owner = user()
    with database().connect() as connection:
        row = (
            connection.execute(select(accounts).where(accounts.c.user_id == owner.id))
            .mappings()
            .one()
        )
        default = connection.execute(
            select(settings.c.default_limit_bytes)
        ).scalar_one()
    assert default == DEFAULT_LIMIT_BYTES == 1024**3
    assert (
        row["override_bytes"] is None
        and row["used_bytes"] == row["reserved_bytes"] == 0
    )
    for override, expected in ((None, 100), (0, 0), (80, 80)):
        result = calculate_usage(
            QuotaAmounts(
                default_limit_bytes=100,
                override_bytes=override,
                used_bytes=20,
                reserved_bytes=10,
            )
        )
        assert result.limit_bytes == expected and result.available_bytes == max(
            0, expected - 30
        )
        assert result.over_limit == (expected < 30)
    over = calculate_usage(
        QuotaAmounts(default_limit_bytes=5, used_bytes=20, reserved_bytes=10)
    )
    assert (
        over.used_bytes == 20
        and over.reserved_bytes == 10
        and over.available_bytes == 0
        and over.over_limit
    )
    exact = calculate_usage(
        QuotaAmounts(default_limit_bytes=30, used_bytes=20, reserved_bytes=10)
    )
    assert not exact.over_limit and exact.available_bytes == 0
    for bad in (-1, True, 1.5, MAX_BYTES + 1):
        with pytest.raises(ValueError):
            QuotaAmounts(default_limit_bytes=bad)


def test_database_rejects_invalid_settings_and_account_counters():
    owner = user()
    for values in (
        {"default_limit_bytes": -1},
        {"default_limit_bytes": MAX_BYTES + 1},
        {"revision": -1},
        {"id": 2},
    ):
        with pytest.raises(IntegrityError):
            with database().begin() as connection:
                connection.execute(update(settings).values(**values))
    for values in (
        {"override_bytes": -1},
        {"used_bytes": -1},
        {"reserved_bytes": -1},
        {"used_bytes": MAX_BYTES, "reserved_bytes": 1},
    ):
        with pytest.raises(IntegrityError):
            with database().begin() as connection:
                connection.execute(
                    update(accounts)
                    .where(accounts.c.user_id == owner.id)
                    .values(**values)
                )
    # Limits may be lowered below charged/reserved bytes without deleting them.
    with database().begin() as connection:
        connection.execute(
            update(accounts)
            .where(accounts.c.user_id == owner.id)
            .values(used_bytes=20, reserved_bytes=10, override_bytes=0)
        )
        connection.execute(update(settings).values(default_limit_bytes=0))
    with database().connect() as connection:
        row = connection.execute(select(accounts)).mappings().one()
        assert row["used_bytes"] == 20 and row["reserved_bytes"] == 10


def test_idempotency_owner_and_result_foreign_keys_are_enforced():
    owner = user()
    other = user("other@example.test")
    first = operation(owner)
    with database().begin() as connection:
        connection.execute(insert(reservations).values(**first))
        connection.execute(insert(reservations).values(**operation(other)))
    with pytest.raises(IntegrityError):
        with database().begin() as connection:
            connection.execute(insert(reservations).values(**operation(owner)))
    wrong = stored(first)
    wrong["owner_id"] = other.id
    with pytest.raises(IntegrityError):
        with database().begin() as connection:
            connection.execute(insert(files).values(**wrong))
    with database().begin() as connection:
        connection.execute(insert(files).values(**stored(first)))
    with pytest.raises(RuntimeError, match="Storage metadata exists"):
        command.downgrade(Config("alembic.ini"), "0002_accounts")
    with database().connect() as connection:
        assert connection.execute(select(files.c.id)).scalar_one() == first["file_id"]
    with pytest.raises(IntegrityError):
        with database().begin() as connection:
            connection.execute(
                delete(reservations).where(reservations.c.id == first["id"])
            )
    with pytest.raises(IntegrityError):
        with database().begin() as connection:
            connection.execute(delete(users).where(users.c.id == owner.id))


def test_lifecycle_records_reject_invalid_states_sizes_and_digests():
    owner = user()
    first = operation(owner)
    for changes in (
        {"state": "unknown"},
        {"purpose": "unknown"},
        {"written_bytes": 1},
        {"allocated_bytes": -1},
        {"expected_bytes": -1},
        {"request_fingerprint": "invalid"},
        {"idempotency_key": " "},
    ):
        invalid = {**first, **changes}
        with pytest.raises(IntegrityError):
            with database().begin() as connection:
                connection.execute(insert(reservations).values(**invalid))
    with database().begin() as connection:
        connection.execute(insert(reservations).values(**first))
    for changes in (
        {"state": "unknown"},
        {"state": "ready"},
        {"state": "deleted"},
        {"size_bytes": -1},
        {"digest": "invalid"},
    ):
        with pytest.raises(IntegrityError):
            with database().begin() as connection:
                connection.execute(insert(files).values(**stored(first, **changes)))
    with database().begin() as connection:
        connection.execute(
            insert(files).values(**stored(first, state="ready", ready_at=now()))
        )
        connection.execute(update(files).values(state="pending_delete"))
        connection.execute(update(files).values(state="deleted", deleted_at=now()))
    with database().connect() as connection:
        assert connection.execute(select(files.c.state)).scalar_one() == "deleted"


def test_migration_backfills_existing_users_and_repeated_upgrade_preserves_data():
    config = Config("alembic.ini")
    command.downgrade(config, "0002_accounts")
    identity = uuid4()
    with database().begin() as connection:
        connection.execute(
            insert(users).values(
                id=identity,
                email="existing@example.test",
                display_name="Ірина",
                password_hash="synthetic-unusable",
            )
        )
    command.upgrade(config, "head")
    with database().begin() as connection:
        row = (
            connection.execute(select(accounts).where(accounts.c.user_id == identity))
            .mappings()
            .one()
        )
        assert (
            row["used_bytes"] == row["reserved_bytes"] == 0
            and row["override_bytes"] is None
        )
        connection.execute(
            update(accounts)
            .where(accounts.c.user_id == identity)
            .values(override_bytes=100, used_bytes=20)
        )
        connection.execute(update(settings).values(default_limit_bytes=200, revision=1))
    command.upgrade(config, "head")
    with database().connect() as connection:
        assert connection.execute(select(accounts.c.used_bytes)).scalar_one() == 20
        assert (
            connection.execute(select(settings.c.default_limit_bytes)).scalar_one()
            == 200
        )


def test_runtime_table_metadata_matches_the_reviewed_migrations():
    from alembic.autogenerate import compare_metadata
    from alembic.runtime.migration import MigrationContext

    from app.accounts.schema import metadata

    with database().connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={
                "include_object": lambda _object, name, kind, _reflected, _other: (
                    not (kind == "table" and name == "test_persistence")
                )
            },
        )
        assert compare_metadata(context, metadata) == []
