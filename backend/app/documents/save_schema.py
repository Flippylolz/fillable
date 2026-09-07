from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.documents.schema import ResourceInfo
from app.storage.schema import ByteCount


class SaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_version_id: UUID
    client_id: UUID
    lease_id: UUID
    document: dict


class SaveInfo(BaseModel):
    resource: ResourceInfo
    saved_version_id: UUID
    saved_number: int
    saved_at: datetime
    saved_size_bytes: ByteCount
    saved_digest: str


class RestoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_version_id: UUID
    client_id: UUID
    lease_id: UUID
