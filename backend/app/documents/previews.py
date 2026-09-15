"""Persist render readiness, reusing the owned immutable revision for previews."""

from sqlalchemy import select

from app.accounts.profile import active_user
from app.documents.schema import ResourceInfo, resources
from app.documents.service import content, query
from app.errors import AppError
from app.infrastructure import database
from app.storage.maintenance import audit


def mark_rendered(state, identity, source_version):
    with database().begin() as connection:
        owner = active_user(connection, state)["id"]
        resource = (
            connection.execute(
                select(resources)
                .where(resources.c.id == identity, resources.c.owner_id == owner)
                .with_for_update()
            )
            .mappings()
            .one_or_none()
        )
        if resource is None or resource["state"] != "active":
            raise AppError(404, "not_found")
        if resource["current_version_id"] != source_version:
            raise AppError(409, "operation_conflict", {"reason": "revision"})
        # One content-free receipt per immutable revision. Its UUID is the
        # revision UUID, allowing indexed lookups without a schema migration.
        audit(
            connection,
            "document_rendered",
            owner,
            owner,
            event_id=source_version,
            version_id=source_version,
        )
        row = (
            connection.execute(query(owner).where(resources.c.id == identity))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise AppError(404, "not_found")
        return ResourceInfo.model_validate(dict(row))


def preview(owner, identity, source_version):
    result = content(owner, identity)
    if (
        not result.resource.preview_ready
        or result.resource.current_version_id != source_version
    ):
        raise AppError(404, "not_found")
    return result
