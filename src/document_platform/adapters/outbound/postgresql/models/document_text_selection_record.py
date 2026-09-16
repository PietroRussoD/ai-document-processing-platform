"""Relational representation of one canonical-text selection."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from document_platform.adapters.outbound.postgresql.metadata import Base


class DocumentTextSelectionRecord(Base):
    __tablename__ = "document_text_selections"
    __table_args__ = (
        CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="processing_run_id_not_nil",
        ),
        CheckConstraint("source IN ('EMBEDDED', 'OCR')", name="source_valid"),
        CheckConstraint(
            "reason IN ('EMBEDDED_SUFFICIENT', 'OCR_HAS_MORE_TEXT', 'EMBEDDED_NOT_WORSE')",
            name="reason_valid",
        ),
        CheckConstraint(
            "(reason = 'EMBEDDED_SUFFICIENT' AND source = 'EMBEDDED') OR "
            "(reason = 'OCR_HAS_MORE_TEXT' AND source = 'OCR') OR "
            "(reason = 'EMBEDDED_NOT_WORSE' AND source = 'EMBEDDED')",
            name="source_matches_reason",
        ),
    )

    processing_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "processing_runs.id",
            name="fk_document_text_selections_processing_run_id_processing_runs",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    source: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(32))
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
