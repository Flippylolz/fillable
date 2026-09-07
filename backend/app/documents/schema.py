from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Table,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.accounts.schema import metadata
from app.storage.schema import ByteCount

resources = Table(
    "documents",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("owner_id", Uuid, nullable=False),
    Column("kind", String(16), nullable=False),
    Column("title", String(160), nullable=False),
    Column("original_filename", String(255), nullable=False),
    Column("original_file_id", Uuid, nullable=False),
    Column("current_version_id", Uuid, nullable=False),
    Column("state", String(16), nullable=False, server_default="active"),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint("id", "owner_id", name="document_owner"),
    ForeignKeyConstraint(
        ["original_file_id", "owner_id"],
        ["stored_files.id", "stored_files.owner_id"],
        ondelete="RESTRICT",
        name="document_original_owner",
    ),
    ForeignKeyConstraint(
        ["current_version_id", "id", "owner_id"],
        [
            "document_versions.id",
            "document_versions.document_id",
            "document_versions.owner_id",
        ],
        deferrable=True,
        initially="DEFERRED",
        use_alter=True,
        name="document_current_version",
    ),
    CheckConstraint("kind IN ('template', 'document')", name="document_kind"),
    CheckConstraint("state IN ('active', 'deleted')", name="document_state"),
    CheckConstraint("length(btrim(title)) > 0", name="document_title"),
)
versions = Table(
    "document_versions",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("document_id", Uuid, nullable=False),
    Column("owner_id", Uuid, nullable=False),
    Column("file_id", Uuid, nullable=False),
    Column("number", Integer, nullable=False),
    Column("document_model", JSONB, nullable=False),
    Column("field_review", JSONB(none_as_null=True)),
    Column("parent_version_id", Uuid),
    Column("restored_from_version_id", Uuid),
    Column("unsupported_count", Integer, nullable=False),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint("id", "document_id", "owner_id", name="version_document_owner"),
    UniqueConstraint("document_id", "number", name="version_number"),
    ForeignKeyConstraint(
        ["document_id", "owner_id"],
        ["documents.id", "documents.owner_id"],
        ondelete="RESTRICT",
        name="version_owner",
    ),
    ForeignKeyConstraint(
        ["file_id", "owner_id"],
        ["stored_files.id", "stored_files.owner_id"],
        ondelete="RESTRICT",
        name="version_file_owner",
    ),
    ForeignKeyConstraint(
        ["parent_version_id", "document_id", "owner_id"],
        [
            "document_versions.id",
            "document_versions.document_id",
            "document_versions.owner_id",
        ],
        ondelete="RESTRICT",
        name="version_parent_owner",
    ),
    ForeignKeyConstraint(
        ["restored_from_version_id", "document_id", "owner_id"],
        [
            "document_versions.id",
            "document_versions.document_id",
            "document_versions.owner_id",
        ],
        ondelete="RESTRICT",
        name="version_restore_owner",
    ),
    CheckConstraint("number > 0 AND unsupported_count >= 0", name="version_bounds"),
)


class UploadMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["template", "document"]
    filename: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=160)

    @field_validator("title")
    @classmethod
    def title_present(cls, value):
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError("blank_title")
        return value


class CopyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_version_id: UUID
    title: str = Field(min_length=1, max_length=160)

    @field_validator("title")
    @classmethod
    def title_present(cls, value):
        return UploadMetadata.title_present(value)


class RenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_version_id: UUID
    previous_title: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=160)

    @field_validator("title", "previous_title")
    @classmethod
    def title_present(cls, value):
        value = UploadMetadata.title_present(value)
        value.encode("utf-8")
        return value


class ResourceInfo(BaseModel):
    id: UUID
    kind: Literal["template", "document"]
    title: str
    original_filename: str
    current_version_id: UUID
    created_at: datetime
    updated_at: datetime
    size_bytes: ByteCount
    digest: str
    unsupported_count: int
    processing_status: Literal[
        "not_started", "queued", "running", "succeeded", "failed", "stale"
    ] = "not_started"
    deletion_pending: bool = False


class DeletionResult(BaseModel):
    status: Literal["pending", "complete"]


class ContentInfo(BaseModel):
    resource: ResourceInfo
    document: dict


class ResourceList(BaseModel):
    items: list[ResourceInfo]
    next_cursor: UUID | None = None
