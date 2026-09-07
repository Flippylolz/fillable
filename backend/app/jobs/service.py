from uuid import uuid4

from sqlalchemy import and_, func, insert, select, update

from app.accounts.profile import active_user
from app.documents.rebase import rebase_discovery
from app.documents.schema import resources
from app.errors import AppError
from app.fields.schema import FieldSnapshot
from app.infrastructure import database
from app.jobs.schema import FieldsResult, ProcessingInfo, jobs
from app.storage.service import now


def resource(connection, owner, identity, *, lock=False):
    query = select(resources).where(
        resources.c.id == identity,
        resources.c.owner_id == owner,
        resources.c.state == "active",
    )
    row = (
        connection.execute(query.with_for_update() if lock else query)
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise AppError(404, "not_found")
    return row


def status(owner, identity):
    with database().connect() as connection:
        document = resource(connection, owner, identity)
        row = (
            connection.execute(
                select(jobs).where(
                    jobs.c.document_id == identity,
                    jobs.c.source_version_id == document["current_version_id"],
                )
            )
            .mappings()
            .one_or_none()
        )
    return (
        ProcessingInfo.model_validate(dict(row))
        if row
        else ProcessingInfo(
            source_version_id=document["current_version_id"],
            status="not_started",
            updated_at=document["updated_at"],
        )
    )


def intent(connection, owner, document):
    identity = document["id"]
    row = (
        connection.execute(
            select(jobs)
            .where(
                jobs.c.document_id == identity,
                jobs.c.source_version_id == document["current_version_id"],
            )
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    if (
        row
        and row["status"] != "failed"
        and not (row["status"] == "succeeded" and row["field_snapshot"] is None)
    ):
        return ProcessingInfo.model_validate(dict(row))
    count = connection.execute(
        select(func.count())
        .select_from(jobs)
        .where(jobs.c.owner_id == owner, jobs.c.status.in_(("queued", "running")))
    ).scalar_one()
    if count >= 5:
        raise AppError(429, "rate_limited")
    if row:
        connection.execute(
            update(jobs)
            .where(jobs.c.id == row["id"])
            .values(
                status="queued",
                attempt=row["attempt"] + 1,
                retry_until=row["attempt"] + 3,
                lease_until=None,
                dispatched_at=None,
                failure_code=None,
                summary=None,
                field_snapshot=None,
                updated_at=now(),
            )
        )
        identity_job = row["id"]
    else:
        identity_job = uuid4()
        connection.execute(
            insert(jobs).values(
                id=identity_job,
                owner_id=owner,
                document_id=identity,
                source_version_id=document["current_version_id"],
            )
        )
    result = (
        connection.execute(select(jobs).where(jobs.c.id == identity_job))
        .mappings()
        .one()
    )
    return ProcessingInfo.model_validate(dict(result))


def submit(state, identity):
    with database().begin() as connection:
        owner = active_user(connection, state)
        document = resource(connection, owner["id"], identity, lock=True)
        return intent(connection, owner["id"], document)


def fields(owner, identity):
    with database().connect() as connection:
        row = (
            connection.execute(
                select(
                    resources.c.current_version_id, jobs.c.status, jobs.c.field_snapshot
                )
                .select_from(resources)
                .outerjoin(
                    jobs,
                    and_(
                        jobs.c.document_id == resources.c.id,
                        jobs.c.source_version_id == resources.c.current_version_id,
                    ),
                )
                .where(
                    resources.c.id == identity,
                    resources.c.owner_id == owner,
                    resources.c.state == "active",
                )
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise AppError(404, "not_found")
    status = row["status"] or "not_started"
    snapshot = None
    if status == "succeeded":
        if row["field_snapshot"] is None:
            status = "not_started"
        else:
            snapshot = FieldSnapshot.model_validate(row["field_snapshot"])
            if snapshot.source_version_id != row["current_version_id"]:
                raise ValueError("stale_field_snapshot")
    return FieldsResult.model_validate(
        {
            "source_version_id": row["current_version_id"],
            "status": status,
            "snapshot": snapshot,
        }
    )


def copy_intent(
    connection, owner, source_version, target, source_model, model, identities
):
    source = (
        connection.execute(
            select(jobs).where(
                jobs.c.owner_id == owner,
                jobs.c.source_version_id == source_version,
                jobs.c.status == "succeeded",
            )
        )
        .mappings()
        .one_or_none()
    )
    if source is None or source["field_snapshot"] is None:
        return intent(connection, owner, target)
    cloned = rebase_discovery(
        source["field_snapshot"],
        source_version,
        source_model,
        target["current_version_id"],
        model,
        identities,
    )
    connection.execute(
        insert(jobs).values(
            id=uuid4(),
            document_id=target["id"],
            owner_id=owner,
            source_version_id=target["current_version_id"],
            status="succeeded",
            summary=source["summary"],
            field_snapshot=cloned.model_dump(mode="json"),
        )
    )
