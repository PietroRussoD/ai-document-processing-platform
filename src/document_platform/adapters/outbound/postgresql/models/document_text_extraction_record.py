"""Relational representation of extracted document text."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from document_platform.adapters.outbound.postgresql.metadata import Base


class DocumentTextExtractionRecord(Base):
    __tablename__ = "document_text_extractions"
    __table_args__ = (
        CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="processing_run_id_not_nil",
        ),
        CheckConstraint("method IN ('PYMUPDF')", name="method_valid"),
        CheckConstraint("quality IN ('SUFFICIENT', 'OCR_RECOMMENDED')", name="quality_valid"),
        CheckConstraint("page_count > 0", name="page_count_positive"),
        CheckConstraint("character_count = char_length(text)", name="character_count_matches_text"),
        CheckConstraint("non_whitespace_character_count >= 0", name="non_whitespace_count_valid"),
    )

    processing_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "processing_runs.id",
            name="fk_document_text_extractions_processing_run_id_processing_runs",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    method: Mapped[str] = mapped_column(String(32))
    quality: Mapped[str] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(Text)
    page_count: Mapped[int] = mapped_column(Integer)
    character_count: Mapped[int] = mapped_column(Integer)
    non_whitespace_character_count: Mapped[int] = mapped_column(Integer)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
