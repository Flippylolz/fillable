"""Persist content-free storage lifecycle and maintenance audit records."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004_storage_audit"
down_revision = "0003_storage_models"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "storage_audit",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")
        ),
        sa.Column(
            "actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("details", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("length(btrim(action)) > 0", name="storage_audit_action"),
    )


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT EXISTS (SELECT 1 FROM storage_audit)"))
        .scalar()
    ):
        raise RuntimeError("Storage audit exists; use a data-preserving recovery")
    op.drop_table("storage_audit")
