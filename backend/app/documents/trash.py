"""Owner-scoped recoverable deletion; retained bytes stay charged until purge."""

from datetime import timedelta

from sqlalchemy import delete, func, select, update

from app.accounts.profile import active_user
from app.documents.deletion import pending_expression, purge
from app.documents.lease_schema import leases
from app.documents.schema import DeletionResult, resources
from app.errors import AppError
from app.infrastructure import database
from app.storage.maintenance import audit
from app.storage.service import lock_account


def owned(connection, state, identity):
    if state.user is None:
        raise AppError(401, "authentication_required")
    lock_account(connection, state.user.id)
    active_user(connection, state)
    row = (
        connection.execute(
            select(resources)
            .where(
                resources.c.id == identity,
                resources.c.owner_id == state.user.id,
            )
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    if row is None or row["state"] == "deleted":
        raise AppError(404, "not_found")
    return row


def move(state, identity):
    with database().begin() as connection:
        row = owned(connection, state, identity)
        if row["state"] == "active":
            now = connection.execute(select(func.clock_timestamp())).scalar_one()
            connection.execute(
                update(resources)
                .where(resources.c.id == identity)
                .values(
                    state="trashed",
                    trashed_at=now,
                    purge_after=now + timedelta(days=30),
                )
            )
            connection.execute(delete(leases).where(leases.c.document_id == identity))
            audit(
                connection,
                "document_trashed",
                row["owner_id"],
                actor=row["owner_id"],
                document_id=identity,
            )
    return DeletionResult(status="complete")


def restore(state, identity):
    with database().begin() as connection:
        row = owned(connection, state, identity)
        if row["state"] == "trashed":
            if (
                row["purge_after"]
                <= connection.execute(select(func.clock_timestamp())).scalar_one()
            ):
                raise AppError(409, "operation_conflict")
            connection.execute(
                update(resources)
                .where(resources.c.id == identity)
                .values(
                    state="active",
                    trashed_at=None,
                    purge_after=None,
                )
            )
            audit(
                connection,
                "document_untrashed",
                row["owner_id"],
                actor=row["owner_id"],
                document_id=identity,
            )
    return DeletionResult(status="complete")


def expire(*, batch=20):
    with database().connect() as connection:
        rows = connection.execute(
            select(resources.c.id, resources.c.owner_id)
            .where(
                resources.c.state == "trashed",
                resources.c.purge_after <= func.clock_timestamp(),
            )
            .order_by(resources.c.purge_after, resources.c.id)
            .limit(batch)
        ).all()
    for row in rows:
        purge(row.owner_id, row.id, expired_only=True)
    return len(rows)


def empty(state):
    if state.user is None:
        raise AppError(401, "authentication_required")
    owner = state.user.id
    with database().begin() as connection:
        lock_account(connection, owner)
        active_user(connection, state)
        # One durable owner-scoped intent covers all pages. Maintenance completes
        # bounded cleanup; restoring any of these items is now forbidden.
        connection.execute(
            update(resources)
            .where(
                resources.c.owner_id == owner,
                resources.c.state == "trashed",
            )
            .values(purge_after=func.clock_timestamp())
        )
        audit(connection, "trash_emptied", owner, actor=owner)
        ids = (
            connection.execute(
                select(resources.c.id)
                .where(
                    resources.c.owner_id == owner,
                    resources.c.state == "trashed",
                )
                .order_by(resources.c.id)
                .limit(20)
            )
            .scalars()
            .all()
        )
    for identity in ids:
        purge(owner, identity, expired_only=True)
    with database().connect() as connection:
        remaining = connection.execute(
            select(resources.c.id)
            .where(
                resources.c.owner_id == owner,
                (resources.c.state == "trashed")
                | ((resources.c.state == "deleted") & pending_expression()),
            )
            .limit(1)
        ).first()
    return DeletionResult(status="pending" if remaining else "complete")
