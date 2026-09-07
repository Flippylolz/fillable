"""Selected revision identity stays distinct from the live current revision."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.storage.schema import ByteCount


class VersionInfo(BaseModel):
    id: UUID
    number: int
    created_at: datetime
    size_bytes: ByteCount
    digest: str
    unsupported_count: int
    is_current: bool


class VersionList(BaseModel):
    current_version_id: UUID
    items: list[VersionInfo]
    next_before: int | None = None


class VersionContent(BaseModel):
    version: VersionInfo
    document: dict
