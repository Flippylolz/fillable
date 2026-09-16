"""Retain recoverable documents and their versions for thirty days."""

import sqlalchemy as sa
from alembic import op

revision = "0014_document_trash"
down_revision = "0013_maintenance_state"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("trashed_at", sa.DateTime(timezone=True)))
    op.add_column("documents", sa.Column("purge_after", sa.DateTime(timezone=True)))
    op.drop_constraint("document_state", "documents", type_="check")
    op.create_check_constraint(
        "document_state", "documents", "state IN ('active', 'trashed', 'deleted')"
    )
    op.create_index("document_trash_expiry", "documents", ["purge_after", "id"])


def downgrade():
    if (
        op.get_bind()
        .execute(
            sa.text("SELECT EXISTS (SELECT 1 FROM documents WHERE state = 'trashed')")
        )
        .scalar_one()
    ):
        raise RuntimeError("Recoverable documents exist; retain the current schema")
    op.drop_index("document_trash_expiry", table_name="documents")
    op.drop_constraint("document_state", "documents", type_="check")
    op.create_check_constraint(
        "document_state", "documents", "state IN ('active', 'deleted')"
    )
    op.drop_column("documents", "purge_after")
    op.drop_column("documents", "trashed_at")
