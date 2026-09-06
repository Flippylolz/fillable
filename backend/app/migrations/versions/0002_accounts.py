"""Local accounts, sessions and authentication attempt windows."""

import sqlalchemy as sa
from alembic import op

revision = "0002_accounts"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("role", sa.String(10), nullable=False, server_default="user"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("ui_language", sa.String(2), nullable=False, server_default="uk"),
        sa.CheckConstraint("role IN ('user', 'admin')", name="users_role"),
        sa.CheckConstraint("ui_language IN ('uk', 'en')", name="users_language"),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])
    op.create_table(
        "login_attempts",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("count", sa.Integer, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_login_attempts_expires_at", "login_attempts", ["expires_at"])


def downgrade():
    op.drop_table("login_attempts")
    op.drop_table("sessions")
    op.drop_table("users")
