"""Durable deletion intent; filesystem cleanup keeps accounting until unlink."""

from sqlalchemy import delete, exists, or_, select, update

from app.accounts.profile import active_user
from app.documents.lease_schema import leases
from app.documents.schema import DeletionResult, resources, versions
from app.errors import AppError
from app.infrastructure import database
from app.jobs.schema import jobs
from app.storage.configuration import configured
from app.storage.maintenance import audit, delete_file
from app.storage.schema import files
from app.storage.service import StorageError, lock_account


def retained(identity, original):
    return or_(
        files.c.id == original,
        files.c.id.in_(
            select(versions.c.file_id).where(versions.c.document_id == identity)
        ),
    )


def pending_expression():
    remaining = files.alias("remaining_document_files")
    return exists(
        select(remaining.c.id)
        .where(
            remaining.c.owner_id == resources.c.owner_id,
            remaining.c.state != "deleted",
            or_(
                remaining.c.id == resources.c.original_file_id,
                remaining.c.id.in_(
                    select(versions.c.file_id)
                    .where(versions.c.document_id == resources.c.id)
                    .correlate(resources)
                ),
            ),
        )
        .correlate(resources)
    )


def remove(state, identity):
    if state.user is None:
        raise AppError(401, "authentication_required")
    owner = state.user.id
    store = configured()
    with database().begin() as connection:
        lock_account(connection, owner)
        active_user(connection, state)
        resource = (
            connection.execute(
                select(resources)
                .where(
                    resources.c.id == identity,
                    resources.c.owner_id == owner,
                )
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if resource is None:
            raise AppError(404, "not_found")
        selected = select(files.c.id).where(
            files.c.owner_id == owner,
            retained(identity, resource["original_file_id"]),
        )
        shared_original = connection.execute(
            select(resources.c.id)
            .where(
                resources.c.id != identity,
                resources.c.original_file_id.in_(selected),
            )
            .limit(1)
        ).first()
        shared_version = connection.execute(
            select(versions.c.id)
            .where(
                versions.c.document_id != identity,
                versions.c.file_id.in_(selected),
            )
            .limit(1)
        ).first()
        if shared_original or shared_version:
            raise AppError(409, "operation_conflict")
        if resource["state"] == "active":
            connection.execute(delete(leases).where(leases.c.document_id == identity))
            connection.execute(
                update(jobs)
                .where(jobs.c.document_id == identity)
                .values(field_snapshot=None)
            )
            connection.execute(
                update(versions)
                .where(versions.c.document_id == identity)
                .values(document_model={}, field_review=None, unsupported_count=0)
            )
            connection.execute(
                update(resources)
                .where(resources.c.id == identity)
                .values(state="deleted")
            )
            connection.execute(
                update(files)
                .where(
                    files.c.id.in_(selected),
                    files.c.state == "ready",
                )
                .values(state="pending_delete")
            )
            audit(
                connection,
                "document_deletion_requested",
                owner,
                actor=state.user.id,
                document_id=identity,
            )
    # Never acquire an FS lock while holding the domain/account SQL transaction.
    with database().connect() as connection:
        pending = (
            connection.execute(
                select(files.c.id)
                .where(
                    files.c.owner_id == owner,
                    retained(identity, resource["original_file_id"]),
                    files.c.state == "pending_delete",
                )
                .order_by(files.c.id)
                .limit(50)
            )
            .scalars()
            .all()
        )
    for file_id in pending:
        try:
            delete_file(store, owner, file_id)
        except StorageError:
            # The durable pending state is retryable, including by reconciliation.
            pass
    with database().connect() as connection:
        remaining = connection.execute(
            select(files.c.id)
            .where(
                files.c.owner_id == owner,
                retained(identity, resource["original_file_id"]),
                files.c.state != "deleted",
            )
            .limit(1)
        ).first()
    return DeletionResult(status="pending" if remaining else "complete")
