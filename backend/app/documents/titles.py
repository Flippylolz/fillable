"""Owned display-title changes; original files and document revisions are untouched."""

from sqlalchemy import func, select, update

from app.accounts.profile import active_user
from app.documents.schema import ResourceInfo, resources
from app.documents.service import query
from app.errors import AppError
from app.infrastructure import database


def rename(state, identity, payload):
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
        if resource["current_version_id"] != payload.source_version_id:
            raise AppError(409, "operation_conflict", {"reason": "revision"})
        if resource["title"] != payload.title:
            if resource["title"] != payload.previous_title:
                raise AppError(409, "operation_conflict", {"reason": "title"})
            connection.execute(
                update(resources)
                .where(resources.c.id == identity)
                .values(title=payload.title, updated_at=func.now())
            )
        row = (
            connection.execute(query(owner).where(resources.c.id == identity))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise AppError(404, "not_found")
        return ResourceInfo.model_validate(dict(row))
