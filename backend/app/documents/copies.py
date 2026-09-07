"""Independent saved-template snapshots through the shared storage transaction."""

import hashlib
import json
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import insert, select

from app.accounts.profile import active_user
from app.documents.rebase import prepare
from app.documents.schema import resources, versions
from app.documents.service import detail, saved_row, working_model
from app.documents.validation import validate_upload
from app.errors import AppError
from app.infrastructure import database
from app.jobs.service import copy_intent
from app.storage.configuration import configured


def create(state, identity, payload, key):
    with database().begin() as connection:
        owner = active_user(connection, state)["id"]
    fingerprint = hashlib.sha256(
        json.dumps(
            {"source": str(identity), **payload.model_dump(mode="json")},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    store = configured()
    snapshot = {}

    def chunks():
        # A committed retry never opens the source, which may since have changed
        # or been deleted. A new copy uses one verified immutable saved revision.
        row = saved_row(owner, identity)
        if row["kind"] != "template":
            raise AppError(422, "invalid_request")
        if row["current_version_id"] != payload.source_version_id:
            raise AppError(409, "operation_conflict")
        snapshot.update(row)
        with store.read(owner, row["file_id"]) as stream:
            data = stream.read(row["size_bytes"])
        package = validate_upload(data, row["original_filename"])
        source_model = working_model(row)
        snapshot["source_model"] = source_model
        review = row["field_review"]
        origin = review.get("sourceVersion") if review else None
        snapshot["prepared"] = prepare(
            source_model,
            package,
            payload.source_version_id,
            UUID(origin) if origin else None,
        )
        yield data

    def finalize(connection, result):
        active_user(connection, state)
        source = (
            connection.execute(
                select(resources)
                .where(resources.c.id == identity, resources.c.owner_id == owner)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if source is None or source["state"] != "active":
            raise AppError(404, "not_found")
        if source["current_version_id"] != payload.source_version_id:
            raise AppError(409, "operation_conflict")
        target = uuid5(NAMESPACE_URL, "fillable:document:" + str(result.id))
        version = uuid5(NAMESPACE_URL, "fillable:initial-version:" + str(result.id))
        model = snapshot["prepared"].bind(version)
        review = model.pop("attrs", {}).get("review")
        connection.execute(
            insert(resources).values(
                id=target,
                owner_id=owner,
                kind="document",
                title=payload.title,
                original_filename=snapshot["original_filename"],
                original_file_id=result.id,
                current_version_id=version,
            )
        )
        connection.execute(
            insert(versions).values(
                id=version,
                document_id=target,
                owner_id=owner,
                file_id=result.id,
                number=1,
                document_model=model,
                field_review=review,
                unsupported_count=snapshot["unsupported_count"],
            )
        )
        copy_intent(
            connection,
            owner,
            payload.source_version_id,
            {"id": target, "current_version_id": version},
            snapshot["source_model"],
            model,
            snapshot["prepared"].identities,
        )

    result = store.store(
        owner, "copy:" + key, fingerprint, "document", chunks(), finalize=finalize
    )
    with database().begin() as connection:
        active_user(connection, state)
    return detail(owner, uuid5(NAMESPACE_URL, "fillable:document:" + str(result.id)))
