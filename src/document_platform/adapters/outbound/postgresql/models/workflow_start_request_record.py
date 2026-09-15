"""Relational representation of a durable workflow-start request."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from document_platform.adapters.outbound.postgresql.metadata import Base


class WorkflowStartRequestRecord(Base):
    __tablename__ = "workflow_start_requests"
    __table_args__ = (
        CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="processing_run_id_not_nil",
        ),
        CheckConstraint(
            "workflow_id = btrim(workflow_id) AND length(workflow_id) > 0",
            name="workflow_id_format",
        ),
        CheckConstraint("status IN ('PENDING', 'DISPATCHING', 'DISPATCHED')", name="status_valid"),
        CheckConstraint(
            "(status = 'DISPATCHED') = (dispatched_at IS NOT NULL)",
            name="dispatch_status_has_time",
        ),
        CheckConstraint(
            "(status = 'DISPATCHING') = "
            "(dispatch_owner IS NOT NULL AND dispatch_token IS NOT NULL "
            "AND lease_expires_at IS NOT NULL)",
            name="dispatching_has_claim",
        ),
        CheckConstraint(
            "lease_expires_at IS NULL OR lease_expires_at > requested_at",
            name="lease_time_ordered",
        ),
        CheckConstraint("attempt_count >= 0", name="attempt_count_not_negative"),
        CheckConstraint(
            "status <> 'PENDING' OR attempt_count = 0",
            name="pending_has_no_attempts",
        ),
        CheckConstraint(
            "status = 'PENDING' OR attempt_count >= 1",
            name="claimed_has_attempt",
        ),
        CheckConstraint(
            "dispatched_at IS NULL OR dispatched_at >= requested_at",
            name="dispatch_time_ordered",
        ),
        CheckConstraint("version >= 0", name="version_not_negative"),
        Index(
            "ix_workflow_start_requests_status_lease_requested_at",
            "status",
            "lease_expires_at",
            "requested_at",
        ),
    )

    processing_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "processing_runs.id",
            name="fk_workflow_start_requests_processing_run_id_processing_runs",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    workflow_id: Mapped[str] = mapped_column(String(128), unique=True)
    status: Mapped[str] = mapped_column(String(16))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatch_owner: Mapped[str | None] = mapped_column(String(64))
    dispatch_token: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer)
