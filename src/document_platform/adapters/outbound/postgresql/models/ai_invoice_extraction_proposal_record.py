"""Relational representation of an immutable AI invoice proposal."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from document_platform.adapters.outbound.postgresql.metadata import Base


class AiInvoiceExtractionProposalRecord(Base):
    __tablename__ = "ai_invoice_extraction_proposals"
    __table_args__ = (
        CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="processing_run_id_not_nil",
        ),
        CheckConstraint("schema_version = 1", name="schema_version_supported"),
        CheckConstraint("provider = 'OLLAMA'", name="provider_supported"),
        CheckConstraint("btrim(model_reference) <> ''", name="model_reference_not_blank"),
        CheckConstraint("btrim(prompt_version) <> ''", name="prompt_version_not_blank"),
        CheckConstraint(
            "selected_text_sha256 ~ '^[0-9a-f]{64}$'",
            name="selected_text_sha256_valid",
        ),
        CheckConstraint(
            "model_digest IS NULL OR model_digest ~ '^(sha256:)?[0-9a-fA-F]{64}$'",
            name="model_digest_valid",
        ),
        CheckConstraint("status IN ('VALID', 'PARTIAL', 'INVALID')", name="status_valid"),
        CheckConstraint(
            "invoice_number IS NULL OR btrim(invoice_number) <> ''",
            name="invoice_number_not_blank",
        ),
        CheckConstraint(
            "supplier_name IS NULL OR btrim(supplier_name) <> ''",
            name="supplier_name_not_blank",
        ),
        CheckConstraint("currency IS NULL OR currency ~ '^[A-Z]{3}$'", name="currency_valid"),
        CheckConstraint(
            "total_amount IS NULL OR total_amount >= 0",
            name="total_amount_not_negative",
        ),
        CheckConstraint("jsonb_typeof(issues) = 'array'", name="issues_array"),
        CheckConstraint(
            "status <> 'VALID' OR (invoice_number IS NOT NULL AND issue_date IS NOT NULL "
            "AND supplier_name IS NOT NULL AND currency IS NOT NULL "
            "AND total_amount IS NOT NULL AND jsonb_array_length(issues) = 0)",
            name="valid_proposal_complete",
        ),
        CheckConstraint(
            "status <> 'PARTIAL' OR ((invoice_number IS NOT NULL OR issue_date IS NOT NULL "
            "OR supplier_name IS NOT NULL OR currency IS NOT NULL OR total_amount IS NOT NULL) "
            "AND jsonb_array_length(issues) > 0)",
            name="partial_proposal_has_fields_and_issues",
        ),
        CheckConstraint(
            "status <> 'INVALID' OR (invoice_number IS NULL AND issue_date IS NULL "
            "AND supplier_name IS NULL AND currency IS NULL AND total_amount IS NULL "
            "AND jsonb_array_length(issues) > 0)",
            name="invalid_proposal_has_no_fields_and_issues",
        ),
    )

    processing_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "processing_runs.id",
            name="fk_ai_invoice_proposals_processing_run_id_processing_runs",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    schema_version: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(32))
    model_reference: Mapped[str] = mapped_column(String(200))
    model_digest: Mapped[str | None] = mapped_column(String(71))
    prompt_version: Mapped[str] = mapped_column(String(100))
    selected_text_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    invoice_number: Mapped[str | None] = mapped_column(String(200))
    issue_date: Mapped[date | None] = mapped_column(Date)
    supplier_name: Mapped[str | None] = mapped_column(String(250))
    currency: Mapped[str | None] = mapped_column(String(3))
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    issues: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
