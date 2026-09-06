"""Document metadata commits in the same transaction as retained storage."""

import hashlib
import json
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import and_, insert, or_, select

from app.accounts.profile import active_user
from app.documents.deletion import pending_expression
from app.documents.package import ARCHIVE_BYTES
from app.documents.schema import ResourceInfo, ResourceList, resources, versions
from app.documents.validation import validate_upload
from app.errors import AppError
from app.infrastructure import database
from app.storage.configuration import configured
from app.storage.schema import files
from app.storage.service import StorageError


def download(owner, identity):
    with database().connect() as connection:
        row = (
            connection.execute(
                query(owner)
                .add_columns(versions.c.file_id)
                .where(resources.c.id == identity)
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise AppError(404, "not_found")
    if row["size_bytes"] > ARCHIVE_BYTES:
        raise StorageError("storage_failure")
    with configured().read(owner, row["file_id"]) as stream:
        data = stream.read(ARCHIVE_BYTES + 1)
    if len(data) != row["size_bytes"]:
        raise StorageError("storage_failure")
    return ResourceInfo.model_validate(dict(row)), data


def query(owner, include_deleting=False):
    visible = and_(resources.c.state == "active", files.c.state == "ready")
    if include_deleting:
        visible = or_(
            visible, and_(resources.c.state == "deleted", pending_expression())
        )
    return (
        select(
            resources,
            files.c.size_bytes,
            files.c.digest,
            versions.c.unsupported_count,
            (resources.c.state == "deleted").label("deletion_pending"),
        )
        .join(versions, versions.c.id == resources.c.current_version_id)
        .join(
            files,
            files.c.id == versions.c.file_id,
        )
        .where(
            resources.c.owner_id == owner,
            visible,
        )
    )


def detail(owner, identity):
    with database().connect() as connection:
        row = (
            connection.execute(query(owner).where(resources.c.id == identity))
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise AppError(404, "not_found")
    return ResourceInfo.model_validate(dict(row))


def listing(owner, kind, limit, cursor):
    statement = query(owner, include_deleting=True).where(resources.c.kind == kind)
    with database().connect() as connection:
        if cursor is not None:
            previous = (
                connection.execute(statement.where(resources.c.id == cursor))
                .mappings()
                .one_or_none()
            )
            if previous is None:
                raise AppError(422, "invalid_request")
            statement = statement.where(
                or_(
                    resources.c.created_at < previous["created_at"],
                    and_(
                        resources.c.created_at == previous["created_at"],
                        resources.c.id < cursor,
                    ),
                )
            )
        rows = (
            connection.execute(
                statement.order_by(
                    resources.c.created_at.desc(), resources.c.id.desc()
                ).limit(limit + 1)
            )
            .mappings()
            .all()
        )
    items = [ResourceInfo.model_validate(dict(row)) for row in rows[:limit]]
    return ResourceList(
        items=items, next_cursor=items[-1].id if len(rows) > limit else None
    )


def upload(state, metadata, data, key):
    if state.user is None:
        raise AppError(401, "authentication_required")
    with database().begin() as connection:
        active_user(connection, state)
    package = validate_upload(data, metadata.filename)
    fingerprint = hashlib.sha256(
        json.dumps(
            {**metadata.model_dump(), "digest": package.digest},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    store = configured()

    def finalize(connection, result):
        active_user(connection, state)
        identity = uuid5(NAMESPACE_URL, "fillable:document:" + str(result.id))
        version = uuid5(NAMESPACE_URL, "fillable:initial-version:" + str(result.id))
        connection.execute(
            insert(resources).values(
                id=identity,
                owner_id=state.user.id,
                kind=metadata.kind,
                title=metadata.title,
                original_filename=metadata.filename,
                original_file_id=result.id,
                current_version_id=version,
            )
        )
        connection.execute(
            insert(versions).values(
                id=version,
                document_id=identity,
                owner_id=state.user.id,
                file_id=result.id,
                number=1,
                document_model=package.model,
                unsupported_count=len(package.unsupported),
            )
        )

    result = store.store(
        state.user.id,
        "upload:" + key,
        fingerprint,
        "original",
        [data],
        expected_bytes=len(data),
        finalize=finalize,
    )
    with database().begin() as connection:
        active_user(connection, state)
    return detail(
        state.user.id, uuid5(NAMESPACE_URL, "fillable:document:" + str(result.id))
    )
