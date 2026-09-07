"""Bounded policy-driven pruning retains provenance and charges until unlink."""

from pydantic import TypeAdapter
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import SQLAlchemyError

from app.documents.retention_schema import KeepLatest, RetentionInfo, settings
from app.documents.schema import resources, versions
from app.infrastructure import database
from app.jobs.schema import jobs
from app.storage.configuration import configured
from app.storage.maintenance import audit, delete_file
from app.storage.schema import files
from app.storage.service import StorageError


def policy(connection, *, lock=False):
    query = select(settings)
    if lock:
        query = query.with_for_update()
    return RetentionInfo.model_validate(
        dict(connection.execute(query).mappings().one())
    )


def configure(keep_latest):
    amount: int | None = TypeAdapter(KeepLatest | None).validate_python(keep_latest)
    with database().begin() as connection:
        previous = policy(connection, lock=True)
        if previous.keep_latest != amount:
            connection.execute(
                update(settings).values(
                    keep_latest=amount, revision=previous.revision + 1
                )
            )
            audit(
                connection,
                "history_retention_configured",
                previous_keep_latest=previous.keep_latest,
                keep_latest=amount,
                policy_revision=previous.revision + 1,
            )
        return policy(connection)


def candidates(keep_latest):
    current = versions.alias("current_history_version")
    return (
        select(
            versions.c.id,
            versions.c.document_id,
            versions.c.owner_id,
            versions.c.file_id,
            files.c.size_bytes,
        )
        .join(resources, resources.c.id == versions.c.document_id)
        .join(current, current.c.id == resources.c.current_version_id)
        .join(files, files.c.id == versions.c.file_id)
        .where(
            resources.c.state == "active",
            files.c.state == "ready",
            versions.c.number > 1,
            versions.c.id != resources.c.current_version_id,
            versions.c.file_id != resources.c.original_file_id,
            versions.c.number <= current.c.number - keep_latest,
        )
    )


def authorize(connection, candidate):
    resource = (
        connection.execute(
            select(resources)
            .where(
                resources.c.id == candidate["document_id"],
                resources.c.owner_id == candidate["owner_id"],
            )
            .with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    current_policy = policy(connection, lock=True)
    if resource is None or current_policy.keep_latest is None:
        raise StorageError("protected_version")
    eligible = connection.execute(
        candidates(current_policy.keep_latest).where(
            versions.c.id == candidate["id"],
            versions.c.file_id == candidate["file_id"],
        )
    ).first()
    if eligible is None:
        raise StorageError("protected_version")
    # Do not remove an accidentally shared legacy file from another document.
    shared = connection.execute(
        select(resources.c.id)
        .where(
            resources.c.id != candidate["document_id"],
            resources.c.original_file_id == candidate["file_id"],
        )
        .limit(1)
    ).first()
    referenced = connection.execute(
        select(versions.c.id)
        .where(
            versions.c.file_id == candidate["file_id"],
            or_(
                versions.c.document_id != candidate["document_id"],
                versions.c.id != candidate["id"],
            ),
        )
        .limit(1)
    ).first()
    if shared or referenced:
        raise StorageError("protected_version")
    connection.execute(
        update(versions)
        .where(versions.c.id == candidate["id"])
        .values(document_model={}, field_review=None)
    )
    connection.execute(
        update(jobs)
        .where(jobs.c.source_version_id == candidate["id"])
        .values(
            field_snapshot=None,
            status="stale",
            lease_until=None,
            updated_at=func.now(),
        )
    )
    audit(
        connection,
        "history_version_pruned",
        candidate["owner_id"],
        document_id=candidate["document_id"],
        version_id=candidate["id"],
        policy_revision=current_policy.revision,
    )


def prune(*, after=None, batch=100):
    if type(batch) is not int or not 1 <= batch <= 100:
        raise ValueError("invalid retention batch")
    with database().connect() as connection:
        current_policy = policy(connection)
        if current_policy.keep_latest is None:
            return {"versions": [], "next_cursor": None, "bytes_removed": 0}
        query = (
            candidates(current_policy.keep_latest)
            .order_by(versions.c.id)
            .limit(batch + 1)
        )
        if after is not None:
            query = query.where(versions.c.id > after)
        rows = connection.execute(query).mappings().all()
    store = configured()
    results, removed = [], 0
    for candidate in rows[:batch]:
        try:
            deleted = delete_file(
                store,
                candidate["owner_id"],
                candidate["file_id"],
                authorize=lambda connection: authorize(connection, candidate),
            )
            status = "pruned" if deleted else "already_deleted"
            if deleted:
                removed += candidate["size_bytes"]
        except StorageError as error:
            status = error.code
        except SQLAlchemyError:
            status = "storage_failure"
        results.append({"version_id": str(candidate["id"]), "status": status})
    return {
        "versions": results,
        "bytes_removed": removed,
        "next_cursor": str(rows[batch - 1]["id"]) if len(rows) > batch else None,
    }
