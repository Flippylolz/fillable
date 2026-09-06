"""Quota and retained-file lifecycle models; no filesystem writes."""

import sqlalchemy as sa
from alembic import op

revision = "0003_storage_models"
down_revision = "0002_accounts"
branch_labels = None
depends_on = None
LIMIT = 9007199254740991


def upgrade():
    op.create_table(
        "storage_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("default_limit_bytes", sa.BigInteger, nullable=False),
        sa.Column("revision", sa.BigInteger, nullable=False, server_default="0"),
        sa.CheckConstraint("id = 1", name="storage_settings_singleton"),
        sa.CheckConstraint(
            f"default_limit_bytes BETWEEN 0 AND {LIMIT}", name="storage_default_bounds"
        ),
        sa.CheckConstraint("revision >= 0", name="storage_settings_revision"),
    )
    op.execute(
        "INSERT INTO storage_settings (id, default_limit_bytes) VALUES (1, 1073741824)"
    )
    op.create_table(
        "storage_accounts",
        sa.Column(
            "user_id",
            sa.Uuid,
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("override_bytes", sa.BigInteger),
        sa.Column("used_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("reserved_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.CheckConstraint(
            f"override_bytes IS NULL OR override_bytes BETWEEN 0 AND {LIMIT}",
            name="storage_override_bounds",
        ),
        sa.CheckConstraint(
            f"used_bytes BETWEEN 0 AND {LIMIT}", name="storage_used_bounds"
        ),
        sa.CheckConstraint(
            f"reserved_bytes BETWEEN 0 AND {LIMIT}", name="storage_reserved_bounds"
        ),
        sa.CheckConstraint(
            f"used_bytes + reserved_bytes <= {LIMIT}", name="storage_total_bounds"
        ),
    )
    op.execute("INSERT INTO storage_accounts (user_id) SELECT id FROM users")
    op.create_table(
        "storage_reservations",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "owner_id",
            sa.Uuid,
            sa.ForeignKey("storage_accounts.user_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("file_id", sa.Uuid, nullable=False, unique=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="reserved"),
        sa.Column("allocated_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("written_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("expected_bytes", sa.BigInteger),
        sa.Column("lease_token", sa.Uuid, nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="reservation_owner_key"
        ),
        sa.UniqueConstraint(
            "id", "file_id", "owner_id", name="reservation_result_owner"
        ),
        sa.CheckConstraint(
            "length(btrim(idempotency_key)) > 0", name="reservation_key_present"
        ),
        sa.CheckConstraint(
            "request_fingerprint ~ '^[0-9a-f]{64}$'", name="reservation_fingerprint"
        ),
        sa.CheckConstraint(
            "purpose IN ('original', 'template', 'document', "
            "'version', 'export', 'preview')",
            name="reservation_purpose",
        ),
        sa.CheckConstraint(
            "state IN ('reserved', 'writing', 'staged', "
            "'committed', 'cleanup_pending', 'aborted')",
            name="reservation_state",
        ),
        sa.CheckConstraint(
            f"allocated_bytes BETWEEN 0 AND {LIMIT}",
            name="reservation_allocation_bounds",
        ),
        sa.CheckConstraint(
            "written_bytes BETWEEN 0 AND allocated_bytes",
            name="reservation_written_bounds",
        ),
        sa.CheckConstraint(
            f"expected_bytes IS NULL OR expected_bytes BETWEEN 0 AND {LIMIT}",
            name="reservation_expected_bounds",
        ),
    )
    op.create_index(
        "ix_storage_reservations_lease_expires_at",
        "storage_reservations",
        ["lease_expires_at"],
    )
    op.create_table(
        "stored_files",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("owner_id", sa.Uuid, nullable=False),
        sa.Column("reservation_id", sa.Uuid, nullable=False, unique=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="staged"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ready_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["reservation_id", "id", "owner_id"],
            [
                "storage_reservations.id",
                "storage_reservations.file_id",
                "storage_reservations.owner_id",
            ],
            ondelete="RESTRICT",
            name="file_reservation_owner",
        ),
        sa.CheckConstraint(
            f"size_bytes BETWEEN 0 AND {LIMIT}", name="file_size_bounds"
        ),
        sa.CheckConstraint("digest ~ '^[0-9a-f]{64}$'", name="file_digest"),
        sa.CheckConstraint(
            "state IN ('staged', 'ready', 'pending_delete', 'deleted')",
            name="file_state",
        ),
        sa.CheckConstraint(
            "state != 'ready' OR ready_at IS NOT NULL", name="file_ready_timestamp"
        ),
        sa.CheckConstraint(
            "state != 'deleted' OR deleted_at IS NOT NULL",
            name="file_deleted_timestamp",
        ),
    )


def downgrade():
    populated = (
        op.get_bind()
        .execute(
            sa.text("""
        SELECT EXISTS (SELECT 1 FROM stored_files)
          OR EXISTS (SELECT 1 FROM storage_reservations)
          OR EXISTS (SELECT 1 FROM storage_accounts
                     WHERE used_bytes != 0 OR reserved_bytes != 0
                        OR override_bytes IS NOT NULL)
          OR EXISTS (SELECT 1 FROM storage_settings
                     WHERE default_limit_bytes != 1073741824 OR revision != 0)
    """)
        )
        .scalar()
    )
    if populated:
        raise RuntimeError("Storage metadata exists; use a data-preserving recovery")
    op.drop_table("stored_files")
    op.drop_table("storage_reservations")
    op.drop_table("storage_accounts")
    op.drop_table("storage_settings")
