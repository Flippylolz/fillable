from typing import Annotated

from pydantic import BaseModel, Field
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
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

# Exact integer representation across PostgreSQL, Python and the browser contract.
MAX_BYTES = 2**53 - 1
DEFAULT_LIMIT_BYTES = 1024**3
ByteCount = Annotated[int, Field(strict=True, ge=0, le=MAX_BYTES)]
PURPOSES = ("original", "template", "document", "version", "export", "preview")
RESERVATION_STATES = (
    "reserved",
    "writing",
    "staged",
    "committed",
    "cleanup_pending",
    "aborted",
)
FILE_STATES = ("staged", "ready", "pending_delete", "deleted")

settings = Table(
    "storage_settings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("default_limit_bytes", BigInteger, nullable=False),
    Column("revision", BigInteger, nullable=False, server_default="0"),
    CheckConstraint("id = 1", name="storage_settings_singleton"),
    CheckConstraint(
        f"default_limit_bytes BETWEEN 0 AND {MAX_BYTES}", name="storage_default_bounds"
    ),
    CheckConstraint("revision >= 0", name="storage_settings_revision"),
)
accounts = Table(
    "storage_accounts",
    metadata,
    Column(
        "user_id", Uuid, ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    ),
    Column("override_bytes", BigInteger),
    Column("used_bytes", BigInteger, nullable=False, server_default="0"),
    Column("reserved_bytes", BigInteger, nullable=False, server_default="0"),
    CheckConstraint(
        f"override_bytes IS NULL OR override_bytes BETWEEN 0 AND {MAX_BYTES}",
        name="storage_override_bounds",
    ),
    CheckConstraint(
        f"used_bytes BETWEEN 0 AND {MAX_BYTES}", name="storage_used_bounds"
    ),
    CheckConstraint(
        f"reserved_bytes BETWEEN 0 AND {MAX_BYTES}", name="storage_reserved_bounds"
    ),
    CheckConstraint(
        f"used_bytes + reserved_bytes <= {MAX_BYTES}", name="storage_total_bounds"
    ),
)
reservations = Table(
    "storage_reservations",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column(
        "owner_id",
        Uuid,
        ForeignKey("storage_accounts.user_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("file_id", Uuid, nullable=False, unique=True),
    Column("idempotency_key", String(128), nullable=False),
    Column("request_fingerprint", String(64), nullable=False),
    Column("purpose", String(16), nullable=False),
    Column("state", String(20), nullable=False, server_default="reserved"),
    Column("allocated_bytes", BigInteger, nullable=False, server_default="0"),
    Column("written_bytes", BigInteger, nullable=False, server_default="0"),
    Column("expected_bytes", BigInteger),
    Column("lease_token", Uuid, nullable=False),
    Column("lease_expires_at", DateTime(timezone=True), nullable=False, index=True),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column(
        "updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    UniqueConstraint("owner_id", "idempotency_key", name="reservation_owner_key"),
    UniqueConstraint("id", "file_id", "owner_id", name="reservation_result_owner"),
    CheckConstraint(
        "length(btrim(idempotency_key)) > 0", name="reservation_key_present"
    ),
    CheckConstraint(
        "request_fingerprint ~ '^[0-9a-f]{64}$'", name="reservation_fingerprint"
    ),
    CheckConstraint(f"purpose IN {PURPOSES}", name="reservation_purpose"),
    CheckConstraint(f"state IN {RESERVATION_STATES}", name="reservation_state"),
    CheckConstraint(
        f"allocated_bytes BETWEEN 0 AND {MAX_BYTES}",
        name="reservation_allocation_bounds",
    ),
    CheckConstraint(
        "written_bytes BETWEEN 0 AND allocated_bytes", name="reservation_written_bounds"
    ),
    CheckConstraint(
        f"expected_bytes IS NULL OR expected_bytes BETWEEN 0 AND {MAX_BYTES}",
        name="reservation_expected_bounds",
    ),
)
files = Table(
    "stored_files",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("owner_id", Uuid, nullable=False),
    Column("reservation_id", Uuid, nullable=False, unique=True),
    Column("size_bytes", BigInteger, nullable=False),
    Column("digest", String(64), nullable=False),
    Column("state", String(20), nullable=False, server_default="staged"),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    Column("ready_at", DateTime(timezone=True)),
    Column("deleted_at", DateTime(timezone=True)),
    ForeignKeyConstraint(
        ["reservation_id", "id", "owner_id"],
        [
            "storage_reservations.id",
            "storage_reservations.file_id",
            "storage_reservations.owner_id",
        ],
        ondelete="RESTRICT",
        name="file_reservation_owner",
    ),
    CheckConstraint(f"size_bytes BETWEEN 0 AND {MAX_BYTES}", name="file_size_bounds"),
    CheckConstraint("digest ~ '^[0-9a-f]{64}$'", name="file_digest"),
    CheckConstraint(f"state IN {FILE_STATES}", name="file_state"),
    CheckConstraint(
        "state != 'ready' OR ready_at IS NOT NULL", name="file_ready_timestamp"
    ),
    CheckConstraint(
        "state != 'deleted' OR deleted_at IS NOT NULL", name="file_deleted_timestamp"
    ),
)

audit_events = Table(
    "storage_audit",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("owner_id", Uuid, ForeignKey("users.id", ondelete="RESTRICT")),
    Column("actor_id", Uuid, ForeignKey("users.id", ondelete="RESTRICT")),
    Column("action", String(64), nullable=False),
    Column("details", JSONB, nullable=False),
    Column(
        "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
    ),
    CheckConstraint("length(btrim(action)) > 0", name="storage_audit_action"),
)


class QuotaAmounts(BaseModel):
    default_limit_bytes: ByteCount
    override_bytes: ByteCount | None = None
    used_bytes: ByteCount = 0
    reserved_bytes: ByteCount = 0


class QuotaUsage(BaseModel):
    limit_bytes: ByteCount
    used_bytes: ByteCount
    reserved_bytes: ByteCount
    available_bytes: ByteCount
    over_limit: bool


def calculate_usage(amounts: QuotaAmounts) -> QuotaUsage:
    limit = (
        amounts.default_limit_bytes
        if amounts.override_bytes is None
        else amounts.override_bytes
    )
    total = amounts.used_bytes + amounts.reserved_bytes
    return QuotaUsage(
        limit_bytes=limit,
        used_bytes=amounts.used_bytes,
        reserved_bytes=amounts.reserved_bytes,
        available_bytes=max(0, limit - total),
        over_limit=total > limit,
    )
