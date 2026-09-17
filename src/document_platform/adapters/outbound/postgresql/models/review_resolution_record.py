"""Relational representation of an immutable manual review resolution."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from document_platform.adapters.outbound.postgresql.metadata import Base


class ReviewResolutionRecord(Base):
    __tablename__ = "review_resolutions"
    __table_args__ = (
        CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="processing_run_id_not_nil",
        ),
        CheckConstraint("decision IN ('APPROVE', 'REJECT')", name="decision_valid"),
        CheckConstraint(
            "length(btrim(reviewer_id)) BETWEEN 1 AND 200",
            name="reviewer_id_valid",
        ),
        CheckConstraint(
            "review_note IS NULL OR length(btrim(review_note)) BETWEEN 1 AND 2000",
            name="review_note_valid",
        ),
    )

    processing_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "processing_runs.id",
            name="fk_review_resolutions_processing_run_id_processing_runs",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    decision: Mapped[str] = mapped_column(String(16))
    reviewer_id: Mapped[str] = mapped_column(String(200))
    review_note: Mapped[str | None] = mapped_column(Text())
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
