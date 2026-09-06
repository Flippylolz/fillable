"""Owned documents and immutable initial versions backed by shared storage."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005_documents"
down_revision = "0004_storage_audit"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint("stored_file_owner", "stored_files", ["id", "owner_id"])
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("original_file_id", sa.Uuid(), nullable=False),
        sa.Column("current_version_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="active"),
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
        sa.UniqueConstraint("id", "owner_id", name="document_owner"),
        sa.ForeignKeyConstraint(
            ["original_file_id", "owner_id"],
            ["stored_files.id", "stored_files.owner_id"],
            ondelete="RESTRICT",
            name="document_original_owner",
        ),
        sa.CheckConstraint("kind IN ('template', 'document')", name="document_kind"),
        sa.CheckConstraint("state IN ('active', 'deleted')", name="document_state"),
        sa.CheckConstraint("length(btrim(title)) > 0", name="document_title"),
    )
    op.create_table(
        "document_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("document_model", JSONB(), nullable=False),
        sa.Column("unsupported_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "id", "document_id", "owner_id", name="version_document_owner"
        ),
        sa.UniqueConstraint("document_id", "number", name="version_number"),
        sa.ForeignKeyConstraint(
            ["document_id", "owner_id"],
            ["documents.id", "documents.owner_id"],
            ondelete="RESTRICT",
            name="version_owner",
        ),
        sa.ForeignKeyConstraint(
            ["file_id", "owner_id"],
            ["stored_files.id", "stored_files.owner_id"],
            ondelete="RESTRICT",
            name="version_file_owner",
        ),
        sa.CheckConstraint(
            "number > 0 AND unsupported_count >= 0", name="version_bounds"
        ),
    )
    op.create_foreign_key(
        "document_current_version",
        "documents",
        "document_versions",
        ["current_version_id", "id", "owner_id"],
        ["id", "document_id", "owner_id"],
        deferrable=True,
        initially="DEFERRED",
    )


def downgrade():
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM documents) "
                "OR EXISTS (SELECT 1 FROM document_versions)"
            )
        )
        .scalar()
    ):
        raise RuntimeError("Documents exist; use a data-preserving recovery")
    op.drop_constraint("document_current_version", "documents", type_="foreignkey")
    op.drop_table("document_versions")
    op.drop_table("documents")
    op.drop_constraint("stored_file_owner", "stored_files", type_="unique")
