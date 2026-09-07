"""Immutable saved bytes and review commit under one revision and lease fence."""

import hashlib
import json
from uuid import UUID

from app.accounts.profile import active_user
from app.documents.export import DocxExport
from app.documents.package import ARCHIVE_BYTES
from app.documents.revision_commit import commit, holder, saved_info
from app.documents.service import saved_row
from app.documents.validation import validate_upload
from app.errors import AppError
from app.fields.working import validate_working
from app.infrastructure import database
from app.storage.configuration import configured


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
        if review is not None and review["sourceVersion"] is None:
            # Bind local native/manual review once, without rewriting editor history.
            review["sourceVersion"] = origin or str(payload.source_version_id)
        with store.read(owner, row["original_file_id"]) as stream:
            original = stream.read(ARCHIVE_BYTES + 1)
        package = validate_upload(original, row["original_filename"])
        data = DocxExport(package).render(document, package.digest)
        prepared.update(
            document=document, review=review, unsupported=len(package.unsupported)
        )
        yield data

    def finalize(connection, result):
        commit(connection, state, identity, payload, owner, result, prepared)

    result = store.store(
        owner, "save:" + key, fingerprint, "version", chunks(), finalize=finalize
    )
    return saved_info(state, owner, identity, result)
