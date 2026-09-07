"""Owner-scoped saved history reads; previews never allocate or mutate versions."""

from sqlalchemy import select

from app.documents.history_schema import VersionContent, VersionInfo, VersionList
from app.documents.package import ARCHIVE_BYTES
from app.documents.schema import resources, versions
from app.documents.service import working_model
from app.errors import AppError
from app.infrastructure import database
from app.storage.configuration import configured
from app.storage.schema import files
from app.storage.service import StorageError


def query(owner, identity):
    return (
        select(
            versions.c.id,
            versions.c.number,
            versions.c.created_at,
            versions.c.unsupported_count,
            files.c.size_bytes,
            files.c.digest,
            (versions.c.id == resources.c.current_version_id).label("is_current"),
        )
        .join(resources, resources.c.id == versions.c.document_id)
        .join(files, files.c.id == versions.c.file_id)
        .where(
            resources.c.id == identity,
            resources.c.owner_id == owner,
            resources.c.state == "active",
            versions.c.owner_id == owner,
            files.c.state == "ready",
        )
    )


def listing(owner, identity, limit, before):
    # Current marker and page share one database snapshot even during a save.
    with (
        database()
        .connect()
        .execution_options(isolation_level="REPEATABLE READ") as connection
    ):
        current = connection.execute(
            select(resources.c.current_version_id).where(
                resources.c.id == identity,
                resources.c.owner_id == owner,
                resources.c.state == "active",
            )
        ).scalar_one_or_none()
        if current is None:
            raise AppError(404, "not_found")
        statement = query(owner, identity)
        if before is not None:
            statement = statement.where(versions.c.number < before)
        rows = (
            connection.execute(
                statement.order_by(versions.c.number.desc()).limit(limit + 1)
            )
            .mappings()
            .all()
        )
    items = [VersionInfo.model_validate(dict(row)) for row in rows[:limit]]
    return VersionList(
        current_version_id=current,
        items=items,
        next_before=items[-1].number if len(rows) > limit else None,
    )


def saved_row(owner, identity, version, *, include_model=False):
    statement = query(owner, identity).add_columns(
        versions.c.file_id, resources.c.original_filename
    )
    if include_model:
        statement = statement.add_columns(
            versions.c.document_model, versions.c.field_review
        )
    with database().connect() as connection:
        row = (
            connection.execute(statement.where(versions.c.id == version))
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise AppError(404, "not_found")
    if row["size_bytes"] > ARCHIVE_BYTES:
        raise StorageError("storage_failure")
    return row


def content(owner, identity, version):
    row = saved_row(owner, identity, version, include_model=True)
    with configured().read(owner, row["file_id"]):
        return VersionContent(
            version=VersionInfo.model_validate(dict(row)), document=working_model(row)
        )


def download(owner, identity, version):
    row = saved_row(owner, identity, version)
    with configured().read(owner, row["file_id"]) as stream:
        data = stream.read(ARCHIVE_BYTES + 1)
    if len(data) != row["size_bytes"]:
        raise StorageError("storage_failure")
    return row["id"], row["original_filename"], data
