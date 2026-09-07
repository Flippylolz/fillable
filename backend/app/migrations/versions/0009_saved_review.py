"""Pair reviewed field metadata with each retained document revision."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009_saved_review"
down_revision = "0008_editing_leases"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "document_versions", sa.Column("field_review", JSONB(none_as_null=True))
    )
    # Older independent copies may already carry working review in their model.
    op.execute("""UPDATE document_versions SET
        field_review = document_model #> '{attrs,review}',
        document_model = document_model - 'attrs'
        WHERE document_model #> '{attrs,review}' IS NOT NULL
        AND document_model #> '{attrs,review}' <> 'null'::jsonb""")


def downgrade():
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM document_versions "
                "WHERE field_review IS NOT NULL)"
            )
        )
        .scalar_one()
    ):
        raise RuntimeError("Saved field review exists; refusing destructive downgrade")
    op.drop_column("document_versions", "field_review")
