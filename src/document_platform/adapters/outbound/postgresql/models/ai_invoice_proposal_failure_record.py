"""Relational representation of terminal AI provider failures."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from document_platform.adapters.outbound.postgresql.metadata import Base


class AiInvoiceProposalFailureRecord(Base):
    __tablename__ = "ai_invoice_proposal_failures"
    __table_args__ = (
        CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="processing_run_id_not_nil",
        ),
        CheckConstraint("provider = 'OLLAMA'", name="provider_supported"),
        CheckConstraint("btrim(model_reference) <> ''", name="model_reference_not_blank"),
        CheckConstraint(
            "code IN ('TIMEOUT', 'UNAVAILABLE', 'INVALID_RESPONSE')",
            name="code_supported",
        ),
    )

    processing_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "processing_runs.id",
            name="fk_ai_proposal_failures_run",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    provider: Mapped[str] = mapped_column(String(32))
    model_reference: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(32))
    failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
