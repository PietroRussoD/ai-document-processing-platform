"""Relational representation of a processing run."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from document_platform.adapters.outbound.postgresql.metadata import Base


class ProcessingRunRecord(Base):
    __tablename__ = "processing_runs"
    __table_args__ = (
        CheckConstraint("id <> '00000000-0000-0000-0000-000000000000'", name="id_not_nil"),
        CheckConstraint(
            "document_id <> '00000000-0000-0000-0000-000000000000'",
            name="document_id_not_nil",
        ),
        CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'WAITING_RETRY', 'REVIEW_REQUIRED', "
            "'COMPLETED', 'FAILED', 'CANCELLED')",
            name="status_valid",
        ),
        CheckConstraint("status_changed_at >= queued_at", name="status_time_ordered"),
        CheckConstraint(
            "started_at IS NULL OR (started_at >= queued_at AND status_changed_at >= started_at)",
            name="started_time_ordered",
        ),
        CheckConstraint(
            "finished_at IS NULL OR "
            "(finished_at >= COALESCE(started_at, queued_at) AND finished_at = status_changed_at)",
            name="finished_time_ordered",
        ),
        CheckConstraint(
            "status <> 'QUEUED' OR started_at IS NULL",
            name="queued_not_started",
        ),
        CheckConstraint(
            "status NOT IN ('RUNNING', 'WAITING_RETRY', 'REVIEW_REQUIRED', 'COMPLETED', 'FAILED') "
            "OR started_at IS NOT NULL",
            name="started_status_has_time",
        ),
        CheckConstraint(
            "(status IN ('COMPLETED', 'FAILED', 'CANCELLED')) = (finished_at IS NOT NULL)",
            name="terminal_status_has_time",
        ),
        CheckConstraint(
            "(started_at IS NULL AND attempt_count = 0) "
            "OR (started_at IS NOT NULL AND attempt_count >= 1)",
            name="attempt_count_consistent",
        ),
        CheckConstraint(
            "previous_run_id IS NULL OR previous_run_id <> id",
            name="previous_run_id_not_self",
        ),
        CheckConstraint("version >= 0", name="version_not_negative"),
        Index("ix_processing_runs_document_id_queued_at", "document_id", "queued_at"),
        Index("ix_processing_runs_previous_run_id", "previous_run_id"),
        Index("ix_processing_runs_status_queued_at", "status", "queued_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "documents.id",
            name="fk_processing_runs_document_id_documents",
            ondelete="CASCADE",
        ),
    )
    previous_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "processing_runs.id",
            name="fk_processing_runs_previous_run_id_processing_runs",
        ),
    )
    status: Mapped[str] = mapped_column(String(32))
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer)
