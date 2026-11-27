import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SavedTranscription(Base):
    __tablename__ = "transcriptions"
    __table_args__ = (
        CheckConstraint("char_length(trim(title)) > 0", name="ck_transcriptions_title_not_blank"),
        CheckConstraint("source_type IN ('recording', 'upload')", name="ck_transcriptions_source_type"),
        CheckConstraint("duration_seconds IS NULL OR duration_seconds >= 0", name="ck_transcriptions_duration_non_negative"),
        Index("ix_transcriptions_created_at", "created_at"),
        Index("ix_transcriptions_detected_language", "detected_language"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    detected_language: Mapped[str | None] = mapped_column(String(16))
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    model_name: Mapped[str | None] = mapped_column(String(255))
    owner_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("anonymous_sessions.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
