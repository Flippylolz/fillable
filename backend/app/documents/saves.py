"""Immutable saved bytes and review commit under one revision and lease fence."""

import hashlib
import json
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import func, insert, select, update

from app.accounts.profile import active_user
from app.accounts.service import token_hash
from app.documents.export import DocxExport
from app.documents.lease_schema import leases
from app.documents.package import ARCHIVE_BYTES
from app.documents.save_schema import SaveInfo
from app.documents.schema import resources, versions
from app.documents.service import detail, saved_row
from app.documents.validation import validate_upload
from app.errors import AppError
from app.fields.working import validate_working
from app.infrastructure import database
from app.jobs.schema import jobs
from app.jobs.service import intent
from app.storage.configuration import configured


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


def save(state, identity, payload, key):
    with database().begin() as connection:
        owner = active_user(connection, state)["id"]
    fingerprint = hashlib.sha256(
        json.dumps(
            {"document_id": str(identity), **payload.model_dump(mode="json")},
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    store = configured()
    prepared: dict[str, object] = {}

    def chunks():
        with database().begin() as connection:
            holder(connection, state, identity, payload)
        row = saved_row(owner, identity)
        if row["current_version_id"] != payload.source_version_id:
            raise AppError(409, "operation_conflict", {"reason": "revision"})
        prior = row["field_review"]
        origin = prior.get("sourceVersion") if prior else None
        document, review = validate_working(
            payload.document,
            payload.source_version_id,
            UUID(origin) if origin else None,
        )
        with store.read(owner, row["original_file_id"]) as stream:
            original = stream.read(ARCHIVE_BYTES + 1)
        package = validate_upload(original, row["original_filename"])
        data = DocxExport(package).render(document, package.digest)
        prepared.update(
            document=document, review=review, unsupported=len(package.unsupported)
        )
        yield data

    def finalize(connection, result):
        holder(connection, state, identity, payload)
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

    result = store.store(
        owner, "save:" + key, fingerprint, "version", chunks(), finalize=finalize
    )
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
