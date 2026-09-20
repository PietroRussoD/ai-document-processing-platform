"""Relational representation of an immutable reprocessing operation."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from document_platform.adapters.outbound.postgresql.metadata import Base


class ReprocessingOperationRecord(Base):
    __tablename__ = "reprocessing_operations"
    __table_args__ = (
        CheckConstraint("id <> '00000000-0000-0000-0000-000000000000'", name="id_not_nil"),
        CheckConstraint(
            "document_id <> '00000000-0000-0000-0000-000000000000'",
            name="document_id_not_nil",
        ),
        CheckConstraint(
            "source_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="source_run_id_not_nil",
        ),
        CheckConstraint(
            "replacement_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="replacement_run_id_not_nil",
        ),
        CheckConstraint("source_run_id <> replacement_run_id", name="source_run_id_differs"),
        CheckConstraint(
            "requested_by = btrim(requested_by) AND length(requested_by) BETWEEN 1 AND 128",
            name="requested_by_format",
        ),
        CheckConstraint(
            "reason = btrim(reason) AND length(reason) BETWEEN 1 AND 500",
            name="reason_format",
        ),
        CheckConstraint(
            "idempotency_key = btrim(idempotency_key) AND idempotency_key ~ '^[ -~]+$'",
            name="idempotency_key_format",
        ),
        CheckConstraint(
            "request_fingerprint ~ '^[0-9a-f]{64}$'",
            name="request_fingerprint_format",
        ),
        UniqueConstraint(
            "document_id",
            "idempotency_key",
            name="uq_reprocessing_operations_document_id_idempotency_key",
        ),
        UniqueConstraint(
            "replacement_run_id",
            name="uq_reprocessing_operations_replacement_run_id",
        ),
        Index("ix_reprocessing_operations_document_id_requested_at", "document_id", "requested_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "documents.id",
            name="fk_reprocessing_operations_document_id_documents",
            ondelete="CASCADE",
        ),
    )
    source_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "processing_runs.id",
            name="fk_reprocessing_operations_source_run_id_processing_runs",
            ondelete="CASCADE",
        ),
    )
    replacement_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "processing_runs.id",
            name="fk_reprocessing_operations_replacement_run_id_processing_runs",
            ondelete="CASCADE",
        ),
    )
    requested_by: Mapped[str] = mapped_column(String(128))
    reason: Mapped[str] = mapped_column(String(500))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
