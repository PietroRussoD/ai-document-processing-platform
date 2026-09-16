"""Relational representation of an immutable structured invoice extraction."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from document_platform.adapters.outbound.postgresql.metadata import Base


class InvoiceExtractionRecord(Base):
    __tablename__ = "invoice_extractions"
    __table_args__ = (
        CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="processing_run_id_not_nil",
        ),
        CheckConstraint(
            "method IN ('DETERMINISTIC_RULES', 'OLLAMA')",
            name="method_valid",
        ),
        CheckConstraint(
            "invoice_number IS NULL OR btrim(invoice_number) <> ''",
            name="number_not_blank",
        ),
        CheckConstraint(
            "supplier_name IS NULL OR btrim(supplier_name) <> ''",
            name="supplier_not_blank",
        ),
        CheckConstraint("currency IS NULL OR currency ~ '^[A-Z]{3}$'", name="currency_valid"),
        CheckConstraint(
            "total_amount IS NULL OR total_amount >= 0",
            name="total_amount_not_negative",
        ),
    )

    processing_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "processing_runs.id",
            name="fk_invoice_extractions_processing_run_id_processing_runs",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    method: Mapped[str] = mapped_column(String(32))
    invoice_number: Mapped[str | None] = mapped_column(String(128))
    issue_date: Mapped[date | None] = mapped_column(Date)
    supplier_name: Mapped[str | None] = mapped_column(String(512))
    currency: Mapped[str | None] = mapped_column(String(3))
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
