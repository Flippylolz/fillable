"""Single active editor generations; originals and retained history are unchanged."""

import sqlalchemy as sa
from alembic import op

revision = "0008_editing_leases"
down_revision = "0007_field_results"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "editing_leases",
        sa.Column("document_id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=False),
        sa.Column("session_hash", sa.String(64), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("lease_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id", "owner_id"],
            ["documents.id", "documents.owner_id"],
            ondelete="CASCADE",
            name="editing_lease_owner",
        ),
        sa.ForeignKeyConstraint(
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


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT EXISTS (SELECT 1 FROM editing_leases)"))
        .scalar_one()
    ):
        raise RuntimeError("Editing leases exist; refusing destructive downgrade")
    op.drop_table("editing_leases")
