"""Add disabled-by-default operator history retention without removing any data."""

import sqlalchemy as sa
from alembic import op

revision = "0011_history_retention"
down_revision = "0010_revision_provenance"
branch_labels = None
depends_on = None


def upgrade():
    table = op.create_table(
        "history_retention_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("keep_latest", sa.Integer()),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="0"),
        sa.CheckConstraint("id = 1", name="history_retention_singleton"),
        sa.CheckConstraint(
            "keep_latest IS NULL OR keep_latest BETWEEN 1 AND 10000",
            name="history_retention_bounds",
        ),
        sa.CheckConstraint("revision >= 0", name="history_retention_revision"),
    )
    op.bulk_insert(table, [{"id": 1, "keep_latest": None, "revision": 0}])


def downgrade():
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM history_retention_settings "
                "WHERE keep_latest IS NOT NULL OR revision <> 0)"
            )
        )
        .scalar_one()
    ):
        raise RuntimeError("Retention policy exists; refusing destructive downgrade")
    op.drop_table("history_retention_settings")
