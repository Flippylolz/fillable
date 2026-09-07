"""Shared save/restore transaction fences and exact immutable result identity."""

from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import func, insert, select, update

from app.accounts.profile import active_user
from app.accounts.service import token_hash
from app.documents.lease_schema import leases
from app.documents.save_schema import SaveInfo
from app.documents.schema import resources, versions
from app.documents.service import detail
from app.errors import AppError
from app.infrastructure import database
from app.jobs.schema import jobs
from app.jobs.service import intent
from app.storage.maintenance import audit
from app.storage.schema import files


def holder(connection, state, identity, payload):
    owner = active_user(connection, state)["id"]
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
    if resource is None or resource["state"] != "active":
        raise AppError(404, "not_found")
    if resource["current_version_id"] != payload.source_version_id:
        raise AppError(409, "operation_conflict", {"reason": "revision"})
    lease = (
        connection.execute(
            select(leases).where(
                leases.c.document_id == identity,
            )
        )
        .mappings()
        .one_or_none()
    )
    now = connection.execute(select(func.clock_timestamp())).scalar_one()
    if (
        lease is None
        or lease["expires_at"] <= now
        or lease["source_version_id"] != payload.source_version_id
        or lease["session_hash"] != token_hash(state.token)
        or lease["client_id"] != payload.client_id
        or lease["lease_id"] != payload.lease_id
    ):
        raise AppError(409, "operation_conflict", {"reason": "lease_lost"})
    return resource


def commit(
    connection, state, identity, payload, owner, result, prepared, restored_from=None
):
    holder(connection, state, identity, payload)
    if restored_from is not None:
        selected = connection.execute(
            select(versions.c.file_id)
            .join(files, files.c.id == versions.c.file_id)
            .where(
                versions.c.id == restored_from,
                versions.c.document_id == identity,
                versions.c.owner_id == owner,
                files.c.state == "ready",
            )
        ).scalar_one_or_none()
        if selected is None or selected != prepared["selected_file"]:
            raise AppError(404, "not_found")
    previous = connection.execute(
        select(versions.c.number).where(
            versions.c.id == payload.source_version_id,
        )
    ).scalar_one()
    version = uuid5(NAMESPACE_URL, "fillable:saved-version:" + str(result.id))
    connection.execute(
        insert(versions).values(
            id=version,
            document_id=identity,
            owner_id=owner,
            file_id=result.id,
            parent_version_id=payload.source_version_id,
            restored_from_version_id=restored_from,
            number=previous + 1,
            document_model=prepared["document"],
            field_review=prepared["review"],
            unsupported_count=prepared["unsupported"],
        )
    )
    connection.execute(
        update(resources)
        .where(resources.c.id == identity)
        .values(
            current_version_id=version,
            updated_at=func.now(),
        )
    )
    connection.execute(
        update(leases)
        .where(leases.c.document_id == identity)
        .values(
            source_version_id=version,
        )
    )
    connection.execute(
        update(jobs)
        .where(
            jobs.c.document_id == identity,
            jobs.c.status.in_(("queued", "running")),
        )
        .values(status="stale", lease_until=None, updated_at=func.now())
    )
    intent(connection, owner, {"id": identity, "current_version_id": version})
    audit(
        connection,
        "revision_restored" if restored_from else "revision_saved",
        owner,
        event_id=uuid5(NAMESPACE_URL, "fillable:revision-audit:" + str(version)),
        actor=owner,
        document_id=identity,
        version_id=version,
        version_number=previous + 1,
        parent_version_id=UUID(str(payload.source_version_id)),
        restored_from_version_id=restored_from,
    )


def saved_info(state, owner, identity, result):
    with database().begin() as connection:
        active_user(connection, state)
        saved = (
            connection.execute(
                select(versions).where(
                    versions.c.id
                    == uuid5(NAMESPACE_URL, "fillable:saved-version:" + str(result.id)),
                    versions.c.owner_id == owner,
                    versions.c.document_id == identity,
                )
            )
            .mappings()
            .one()
        )
    return SaveInfo(
        resource=detail(owner, identity),
        saved_version_id=saved["id"],
        saved_number=saved["number"],
        saved_at=saved["created_at"],
        saved_size_bytes=result.size_bytes,
        saved_digest=result.digest,
    )
