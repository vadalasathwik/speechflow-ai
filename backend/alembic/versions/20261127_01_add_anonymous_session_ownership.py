"""add anonymous session ownership

Revision ID: 20261127_01
Revises: 20261126_01
Create Date: 2026-11-27
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261127_01"
down_revision = "20261126_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "anonymous_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_anonymous_sessions_expires_at", "anonymous_sessions", ["expires_at"])
    op.add_column("transcriptions", sa.Column("owner_session_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_transcriptions_owner_session", "transcriptions", "anonymous_sessions", ["owner_session_id"], ["id"])
    op.create_index("ix_transcriptions_owner_session_id", "transcriptions", ["owner_session_id"])


def downgrade() -> None:
    op.drop_index("ix_transcriptions_owner_session_id", table_name="transcriptions")
    op.drop_constraint("fk_transcriptions_owner_session", "transcriptions", type_="foreignkey")
    op.drop_column("transcriptions", "owner_session_id")
    op.drop_index("ix_anonymous_sessions_expires_at", table_name="anonymous_sessions")
    op.drop_table("anonymous_sessions")
