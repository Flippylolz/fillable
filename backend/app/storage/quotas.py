"""Read usage and perform trusted container-operator allocation changes."""

from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy import select, update

from app.accounts.schema import users
from app.errors import AppError
from app.infrastructure import database
from app.storage.maintenance import audit
from app.storage.schema import (
    ByteCount,
    QuotaAmounts,
    accounts,
    calculate_usage,
    settings,
)
from app.storage.service import lock_account

BYTES = TypeAdapter(ByteCount)


def _usage(connection, owner):
    row = (
        connection.execute(
            select(accounts, settings.c.default_limit_bytes)
            .select_from(accounts.join(settings, settings.c.id == 1))
            .where(accounts.c.user_id == owner)
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise AppError(404, "not_found")
    return calculate_usage(
        QuotaAmounts(
            default_limit_bytes=row["default_limit_bytes"],
            override_bytes=row["override_bytes"],
            used_bytes=row["used_bytes"],
            reserved_bytes=row["reserved_bytes"],
        )
    )


def usage(owner: UUID):
    with database().connect() as connection:
        return _usage(connection, owner)


def owner_for_email(email: str):
    with database().connect() as connection:
        owner = connection.execute(
            select(users.c.id).where(
                users.c.email == email.strip().casefold(),
            )
        ).scalar_one_or_none()
    if owner is None:
        raise AppError(404, "not_found")
    return owner


def set_default(amount: int):
    amount = BYTES.validate_python(amount)
    with database().begin() as connection:
        row = connection.execute(select(settings).with_for_update()).mappings().one()
        revision = row["revision"]
        if amount != row["default_limit_bytes"]:
            revision += 1
            connection.execute(
                update(settings).values(
                    default_limit_bytes=amount,
                    revision=revision,
                )
            )
            audit(
                connection,
                "quota_default_changed",
                before=row["default_limit_bytes"],
                after=amount,
                revision=revision,
            )
        return {"default_limit_bytes": amount, "revision": revision}


def set_override(owner: UUID, amount: int | None):
    if amount is not None:
        amount = BYTES.validate_python(amount)
    with database().begin() as connection:
        account, _ = lock_account(connection, owner)
        if account["override_bytes"] != amount:
            connection.execute(
                update(accounts)
                .where(accounts.c.user_id == owner)
                .values(
                    override_bytes=amount,
                )
            )
            audit(
                connection,
                "quota_override_changed",
                owner,
                before=account["override_bytes"],
                after=amount,
            )
        return _usage(connection, owner)
