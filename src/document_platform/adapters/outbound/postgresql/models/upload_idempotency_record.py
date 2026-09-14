"""Relational representation of an upload idempotency record."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from document_platform.adapters.outbound.postgresql.metadata import Base


class UploadIdempotencyRecordRow(Base):
    __tablename__ = "upload_idempotency_records"
    __table_args__ = (
        CheckConstraint(
            "idempotency_key = btrim(idempotency_key) AND idempotency_key ~ '^[ -~]+$'",
            name="key_format",
        ),
        CheckConstraint(
            "request_fingerprint ~ '^[0-9a-f]{64}$'",
            name="fingerprint_format",
        ),
        CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="run_id_not_nil",
        ),
        Index("ix_upload_idempotency_records_recorded_at", "recorded_at"),
    )

    idempotency_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    processing_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "processing_runs.id",
            name="fk_upload_idempotency_records_processing_run_id_processing_runs",
            ondelete="CASCADE",
        ),
        unique=True,
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
