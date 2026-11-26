"""create transcriptions table

Revision ID: 20261126_01
Revises:
Create Date: 2026-11-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261126_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transcriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("detected_language", sa.String(length=16), nullable=True),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("char_length(trim(title)) > 0", name="ck_transcriptions_title_not_blank"),
        sa.CheckConstraint("source_type IN ('recording', 'upload')", name="ck_transcriptions_source_type"),
        sa.CheckConstraint("duration_seconds IS NULL OR duration_seconds >= 0", name="ck_transcriptions_duration_non_negative"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transcriptions_created_at", "transcriptions", ["created_at"])
    op.create_index("ix_transcriptions_detected_language", "transcriptions", ["detected_language"])


def downgrade() -> None:
    op.drop_index("ix_transcriptions_detected_language", table_name="transcriptions")
    op.drop_index("ix_transcriptions_created_at", table_name="transcriptions")
    op.drop_table("transcriptions")
