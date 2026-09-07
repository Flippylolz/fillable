"""Keep same-document parent and restore provenance for retained history."""

import sqlalchemy as sa
from alembic import op

revision = "0010_revision_provenance"
down_revision = "0009_saved_review"
branch_labels = None
depends_on = None


def upgrade():
    for column, name in (
        ("parent_version_id", "version_parent_owner"),
        ("restored_from_version_id", "version_restore_owner"),
    ):
        op.add_column("document_versions", sa.Column(column, sa.Uuid()))
        op.create_foreign_key(
            name,
            "document_versions",
            "document_versions",
            [column, "document_id", "owner_id"],
            ["id", "document_id", "owner_id"],
            ondelete="RESTRICT",
        )
    op.execute("""WITH prior AS (
        SELECT id, lag(id) OVER (PARTITION BY document_id ORDER BY number) AS parent
        FROM document_versions
    ) UPDATE document_versions AS version SET parent_version_id = prior.parent
      FROM prior WHERE version.id = prior.id""")


def downgrade():
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM document_versions WHERE "
                "parent_version_id IS NOT NULL OR restored_from_version_id IS NOT NULL)"
            )
        )
        .scalar_one()
    ):
        raise RuntimeError("Revision provenance exists; refusing destructive downgrade")
    for column, name in (
        ("restored_from_version_id", "version_restore_owner"),
        ("parent_version_id", "version_parent_owner"),
    ):
        op.drop_constraint(name, "document_versions", type_="foreignkey")
        op.drop_column("document_versions", column)
