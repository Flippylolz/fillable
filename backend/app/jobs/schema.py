from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Table,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.documents.schema import resources

jobs = Table(
    "processing_jobs",
    resources.metadata,
    Column("id", Uuid, primary_key=True),
    Column("document_id", Uuid, nullable=False),
    Column("owner_id", Uuid, nullable=False),
    Column("source_version_id", Uuid, nullable=False),
    Column("status", String(16), nullable=False, server_default="queued"),
    Column("attempt", Integer, nullable=False, server_default="1"),
    Column("retry_until", Integer, nullable=False, server_default="3"),
    Column("lease_until", DateTime(timezone=True)),
    Column("dispatched_at", DateTime(timezone=True)),
    Column("failure_code", String(32)),
    Column("summary", JSONB),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    ForeignKeyConstraint(
        ["source_version_id", "document_id", "owner_id"],
        [
            "document_versions.id",
            "document_versions.document_id",
            "document_versions.owner_id",
        ],
        name="processing_version_owner",
        ondelete="RESTRICT",
    ),
    UniqueConstraint("document_id", "source_version_id", name="processing_revision"),
    CheckConstraint(
        "status IN ('queued', 'running', 'succeeded', 'failed', 'stale')",
        name="processing_status",
    ),
    CheckConstraint(
        "attempt >= 1 AND retry_until >= attempt AND retry_until - attempt <= 2",
        name="processing_attempts",
    ),
    CheckConstraint(
        "(status = 'running') = (lease_until IS NOT NULL)", name="processing_lease"
    ),
    Index("processing_dispatch", "status", "dispatched_at"),
    Index("processing_owner", "owner_id", "status"),
)


class ProcessingInfo(BaseModel):
    id: UUID | None = None
    source_version_id: UUID
    status: Literal["not_started", "queued", "running", "succeeded", "failed", "stale"]
    attempt: int = Field(ge=0, default=0)
    updated_at: datetime
    failure_code: Literal["processing_failed"] | None = None
    summary: dict[str, int] | None = None
