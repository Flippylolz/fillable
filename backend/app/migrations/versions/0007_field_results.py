"""Validated discovery results belong to the processed source revision."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007_field_results"
down_revision = "0006_processing_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "processing_jobs", sa.Column("field_snapshot", JSONB(none_as_null=True))
    )


def downgrade():
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM processing_jobs "
                "WHERE field_snapshot IS NOT NULL)"
            )
        )
        .scalar_one()
    ):
        raise RuntimeError("Field results exist; refusing destructive downgrade")
    op.drop_column("processing_jobs", "field_snapshot")
