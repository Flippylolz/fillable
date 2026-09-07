"""Persist bounded maintenance progress without modifying document data."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0013_maintenance_state"
down_revision = "0012_audit_chronology"
branch_labels = None
depends_on = None


def upgrade():
    table = op.create_table(
        "maintenance_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Uuid()),
        sa.Column("status", sa.String(16), nullable=False, server_default="idle"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column(
            "interrupted_runs", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column("operations_cursor", sa.Uuid()),
        sa.Column("accounts_cursor", sa.Uuid()),
        sa.Column("retention_cursor", sa.Uuid()),
        sa.Column("summary", JSONB(), nullable=False, server_default="{}"),
        sa.CheckConstraint("id = 1", name="maintenance_singleton"),
        sa.CheckConstraint(
            "status IN ('idle', 'running', 'succeeded', 'failed')",
            name="maintenance_status",
        ),
        sa.CheckConstraint("interrupted_runs >= 0", name="maintenance_interruptions"),
    )
    op.bulk_insert(table, [{"id": 1}])


def downgrade():
    if (
        op.get_bind()
        .execute(
            sa.text("SELECT run_id IS NOT NULL FROM maintenance_state WHERE id = 1")
        )
        .scalar_one()
    ):
        raise RuntimeError("Maintenance history exists; retain the current schema")
    op.drop_table("maintenance_state")
