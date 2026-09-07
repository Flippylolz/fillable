"""An editing holder is an authenticated session, tab and server generation."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import Column, DateTime, ForeignKeyConstraint, String, Table, Uuid

from app.accounts.schema import metadata

leases = Table(
    "editing_leases",
    metadata,
    Column("document_id", Uuid, primary_key=True),
    Column("owner_id", Uuid, nullable=False),
    Column("source_version_id", Uuid, nullable=False),
    Column("session_hash", String(64), nullable=False),
    Column("client_id", Uuid, nullable=False),
    Column("lease_id", Uuid, nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["document_id", "owner_id"],
        ["documents.id", "documents.owner_id"],
        ondelete="CASCADE",
        name="editing_lease_owner",
    ),
    ForeignKeyConstraint(
        ["source_version_id", "document_id", "owner_id"],
        [
            "document_versions.id",
            "document_versions.document_id",
            "document_versions.owner_id",
        ],
        ondelete="RESTRICT",
        name="editing_lease_version",
    ),
)


class LeaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["acquire", "renew", "release"]
    source_version_id: UUID
    client_id: UUID
    lease_id: UUID | None = None

    @model_validator(mode="after")
    def generation(self):
        if (self.action == "acquire") != (self.lease_id is None):
            raise ValueError("lease_generation_required_for_renewal_and_release")
        return self


class LeaseInfo(BaseModel):
    status: Literal["active", "released"]
    source_version_id: UUID
    lease_id: UUID
    expires_at: datetime | None
    valid_for_seconds: int
