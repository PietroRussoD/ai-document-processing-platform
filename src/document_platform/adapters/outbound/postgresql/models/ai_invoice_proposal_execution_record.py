"""Relational representation of advisory execution progress."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from document_platform.adapters.outbound.postgresql.metadata import Base


class AiInvoiceProposalExecutionRecord(Base):
    __tablename__ = "ai_invoice_proposal_executions"
    __table_args__ = (
        CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="processing_run_id_not_nil",
        ),
        CheckConstraint(
            "status IN ('DISABLED', 'RUNNING', 'COMPLETED', 'FAILED')",
            name="status_supported",
        ),
        CheckConstraint(
            "(status = 'DISABLED' AND started_at IS NULL AND finished_at IS NOT NULL "
            "AND finished_at = status_changed_at) OR "
            "(status = 'RUNNING' AND started_at IS NOT NULL AND finished_at IS NULL "
            "AND started_at = status_changed_at) OR "
            "(status IN ('COMPLETED', 'FAILED') AND started_at IS NOT NULL "
            "AND finished_at IS NOT NULL AND finished_at = status_changed_at "
            "AND started_at <= finished_at)",
            name="lifecycle_times_valid",
        ),
    )

    processing_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "processing_runs.id",
            name="fk_ai_proposal_executions_run",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(String(32))
    status_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
