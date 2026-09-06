"""Durable per-revision processing intent, attempts and state."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006_processing_jobs"
down_revision = "0005_documents"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("retry_until", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("dispatched_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(32)),
        sa.Column("summary", JSONB),
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
        sa.ForeignKeyConstraint(
            ["source_version_id", "document_id", "owner_id"],
            [
                "document_versions.id",
                "document_versions.document_id",
                "document_versions.owner_id",
            ],
            name="processing_version_owner",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "document_id", "source_version_id", name="processing_revision"
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'stale')",
            name="processing_status",
        ),
        sa.CheckConstraint(
            "attempt >= 1 AND retry_until >= attempt AND retry_until - attempt <= 2",
            name="processing_attempts",
        ),
        sa.CheckConstraint(
            "(status = 'running') = (lease_until IS NOT NULL)", name="processing_lease"
        ),
    )
    op.create_index(
        "processing_dispatch", "processing_jobs", ["status", "dispatched_at"]
    )
    op.create_index("processing_owner", "processing_jobs", ["owner_id", "status"])


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT EXISTS (SELECT 1 FROM processing_jobs)"))
        .scalar_one()
    ):
        raise RuntimeError("Processing jobs exist; refusing destructive downgrade")
    op.drop_table("processing_jobs")
