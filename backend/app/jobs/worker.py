"""Only opaque job/attempt arguments enter RQ; source content stays local."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from app.accounts.schema import users
from app.documents.package import ARCHIVE_BYTES, InvalidDocument
from app.documents.schema import resources, versions
from app.documents.validation import validate_upload
from app.infrastructure import database
from app.jobs.schema import jobs
from app.storage.configuration import configured
from app.storage.service import now

JOB_SECONDS = 30
LEASE_SECONDS = 45


def locked(connection, identity):
    reference = (
        connection.execute(select(jobs).where(jobs.c.id == identity))
        .mappings()
        .one_or_none()
    )
    if reference is None:
        return None, None
    document = (
        connection.execute(
            select(resources, users.c.active.label("owner_active"))
            .join(users, users.c.id == resources.c.owner_id)
            .where(resources.c.id == reference["document_id"])
            .with_for_update(of=resources)
        )
        .mappings()
        .one()
    )
    job = (
        connection.execute(select(jobs).where(jobs.c.id == identity).with_for_update())
        .mappings()
        .one()
    )
    return document, job


def stale(document, job):
    return (
        not document["owner_active"]
        or document["state"] != "active"
        or document["current_version_id"] != job["source_version_id"]
    )


def claim(identity, attempt):
    with database().begin() as connection:
        document, job = locked(connection, identity)
        if job is None or job["attempt"] != attempt or job["status"] != "queued":
            return None
        if stale(document, job):
            connection.execute(
                update(jobs)
                .where(jobs.c.id == identity)
                .values(status="stale", lease_until=None, updated_at=now())
            )
            return None
        file_id = connection.execute(
            select(versions.c.file_id).where(versions.c.id == job["source_version_id"])
        ).scalar_one()
        connection.execute(
            update(jobs)
            .where(jobs.c.id == identity)
            .values(
                status="running",
                lease_until=now() + timedelta(seconds=LEASE_SECONDS),
                updated_at=now(),
            )
        )
    return job["owner_id"], file_id, document["original_filename"]


def inspect_file(owner, file_id, filename):
    with configured().read(owner, file_id) as stream:
        data = stream.read(ARCHIVE_BYTES + 1)
    if len(data) > ARCHIVE_BYTES:
        raise InvalidDocument("archive_limit")
    package = validate_upload(data, filename)
    result = {
        "supported_controls": 0,
        "paragraphs": 0,
        "unsupported_features": len(package.unsupported),
    }
    nodes = [package.model]
    while nodes:
        node = nodes.pop()
        result["supported_controls"] += node["type"] == "field"
        result["paragraphs"] += node["type"] == "paragraph"
        nodes.extend(node.get("content", []))
    return result


def finish(identity, attempt, summary):
    with database().begin() as connection:
        document, job = locked(connection, identity)
        if job is None or job["attempt"] != attempt or job["status"] != "running":
            return
        if job["lease_until"] <= now():
            return
        values: dict[str, object] = {"lease_until": None, "updated_at": now()}
        if stale(document, job):
            values.update(status="stale")
        elif summary is not None:
            values.update(status="succeeded", summary=summary, failure_code=None)
        elif attempt < job["retry_until"]:
            values.update(status="queued", attempt=attempt + 1, dispatched_at=None)
        else:
            values.update(status="failed", failure_code="processing_failed")
        connection.execute(update(jobs).where(jobs.c.id == identity).values(**values))


def process(identity, attempt):
    try:
        identity = UUID(identity)
        claimed = claim(identity, attempt)
        if claimed is None:
            return
        try:
            summary = inspect_file(*claimed)
        except Exception:
            # Do not send parser/file exception messages or content to RQ logs.
            summary = None
        finish(identity, attempt, summary)
    except (ValueError, SQLAlchemyError):
        # Durable lease/intent is recovered after database interruption.
        return
