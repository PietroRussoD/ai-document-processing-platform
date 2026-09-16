"""Relational representation of an immutable document classification."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from document_platform.adapters.outbound.postgresql.metadata import Base


class DocumentClassificationRecord(Base):
    __tablename__ = "document_classifications"
    __table_args__ = (
        CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="processing_run_id_not_nil",
        ),
        CheckConstraint(
            "document_type IN ('INVOICE', 'PURCHASE_ORDER', 'CREDIT_NOTE', 'UNKNOWN')",
            name="document_type_valid",
        ),
        CheckConstraint(
            "reason IN ('KEYWORD_MATCHED', 'NO_MATCH', 'AMBIGUOUS_MATCH')",
            name="reason_valid",
        ),
        CheckConstraint(
            "(document_type = 'UNKNOWN') = (reason <> 'KEYWORD_MATCHED')",
            name="type_matches_reason",
        ),
    )

    processing_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "processing_runs.id",
            name="fk_document_classifications_processing_run_id_processing_runs",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    document_type: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(String(32))
    classified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
