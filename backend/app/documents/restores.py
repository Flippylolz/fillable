"""Restore an exact saved pair into an independently charged new revision."""

import hashlib
import json
from uuid import UUID

from app.accounts.profile import active_user
from app.documents.history import saved_row
from app.documents.package import ARCHIVE_BYTES
from app.documents.rebase import correspondence
from app.documents.revision_commit import commit, holder, saved_info
from app.documents.service import working_model
from app.documents.validation import validate_upload
from app.fields.working import validate_working
from app.infrastructure import database
from app.storage.configuration import configured
from app.storage.service import StorageError


def restore(state, identity, selected, payload, key):
    with database().begin() as connection:
        owner = active_user(connection, state)["id"]
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "document_id": str(identity),
                "selected": str(selected),
                **payload.model_dump(mode="json"),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    store = configured()
    prepared: dict[str, object] = {}

    def chunks():
        with database().begin() as connection:
            holder(connection, state, identity, payload)
        row = saved_row(owner, identity, selected, include_model=True)
        with store.read(owner, row["file_id"]) as stream:
            data = stream.read(ARCHIVE_BYTES + 1)
        if len(data) != row["size_bytes"]:
            raise StorageError("storage_failure")
        package = validate_upload(data, row["original_filename"])
        prior = row["field_review"]
        origin = prior.get("sourceVersion") if prior else None
        document, review = validate_working(
            working_model(row),
            selected,
            UUID(origin) if origin else None,
        )
        correspondence(document, package)
        prepared.update(
            document=document,
            review=review,
            unsupported=row["unsupported_count"],
            selected_file=row["file_id"],
        )
        yield data

    def finalize(connection, result):
        commit(connection, state, identity, payload, owner, result, prepared, selected)

    result = store.store(
        owner, "restore:" + key, fingerprint, "version", chunks(), finalize=finalize
    )
    return saved_info(state, owner, identity, result)
