"""Relational representation of immutable operator invoice corrections."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from document_platform.adapters.outbound.postgresql.metadata import Base


class InvoiceReviewCorrectionRecord(Base):
    __tablename__ = "invoice_review_corrections"
    __table_args__ = (
        CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="processing_run_id_not_nil",
        ),
        CheckConstraint(
            "field IN ('INVOICE_NUMBER', 'ISSUE_DATE', 'SUPPLIER_NAME', 'CURRENCY', "
            "'TOTAL_AMOUNT')",
            name="field_valid",
        ),
        CheckConstraint("source IN ('MANUAL', 'AI_PROPOSAL')", name="source_valid"),
        CheckConstraint(
            "(field IN ('INVOICE_NUMBER', 'SUPPLIER_NAME', 'CURRENCY') "
            "AND corrected_text IS NOT NULL AND corrected_date IS NULL "
            "AND corrected_amount IS NULL) "
            "OR (field = 'ISSUE_DATE' AND corrected_text IS NULL "
            "AND corrected_date IS NOT NULL AND corrected_amount IS NULL) "
            "OR (field = 'TOTAL_AMOUNT' AND corrected_text IS NULL "
            "AND corrected_date IS NULL AND corrected_amount IS NOT NULL)",
            name="value_shape_valid",
        ),
        CheckConstraint(
            "(field = 'INVOICE_NUMBER' AND length(btrim(corrected_text)) BETWEEN 1 AND 128) "
            "OR (field = 'SUPPLIER_NAME' AND length(btrim(corrected_text)) BETWEEN 1 AND 512) "
            "OR (field = 'CURRENCY' AND corrected_text ~ '^[A-Z]{3}$') "
            "OR field IN ('ISSUE_DATE', 'TOTAL_AMOUNT')",
            name="text_value_valid",
        ),
        CheckConstraint(
            "field <> 'TOTAL_AMOUNT' OR corrected_amount > 0",
            name="amount_positive",
        ),
    )

    processing_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "review_resolutions.processing_run_id",
            name="fk_invoice_review_corrections_run_id_review_resolutions",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    field: Mapped[str] = mapped_column(String(32), primary_key=True)
    source: Mapped[str] = mapped_column(
        String(16), default="MANUAL", server_default=text("'MANUAL'")
    )
    corrected_text: Mapped[str | None] = mapped_column(String(512))
    corrected_date: Mapped[date | None] = mapped_column(Date())
    corrected_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    corrected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
