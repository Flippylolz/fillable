"""Index bounded chronological audit pages without modifying retained events."""

from alembic import op

revision = "0012_audit_chronology"
down_revision = "0011_history_retention"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("storage_audit_chronology", "storage_audit", ["created_at", "id"])


def downgrade():
    op.drop_index("storage_audit_chronology", table_name="storage_audit")
