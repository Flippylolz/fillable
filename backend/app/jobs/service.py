from uuid import uuid4

from sqlalchemy import func, insert, select, update

from app.accounts.profile import active_user
from app.documents.schema import resources
from app.errors import AppError
from app.infrastructure import database
from app.jobs.schema import ProcessingInfo, jobs
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


def submit(state, identity):
    with database().begin() as connection:
        owner = active_user(connection, state)
        document = resource(connection, owner["id"], identity, lock=True)
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
        if row and row["status"] != "failed":
            return ProcessingInfo.model_validate(dict(row))
        count = connection.execute(
            select(func.count())
            .select_from(jobs)
            .where(
                jobs.c.owner_id == owner["id"], jobs.c.status.in_(("queued", "running"))
            )
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
                    updated_at=now(),
                )
            )
            identity_job = row["id"]
        else:
            identity_job = uuid4()
            connection.execute(
                insert(jobs).values(
                    id=identity_job,
                    owner_id=owner["id"],
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
