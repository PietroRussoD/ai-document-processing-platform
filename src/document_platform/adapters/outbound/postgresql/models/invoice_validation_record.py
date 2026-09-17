"""Relational representation of an immutable invoice validation."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from document_platform.adapters.outbound.postgresql.metadata import Base


class InvoiceValidationRecord(Base):
    __tablename__ = "invoice_validations"
    __table_args__ = (
        CheckConstraint(
            "processing_run_id <> '00000000-0000-0000-0000-000000000000'",
            name="processing_run_id_not_nil",
        ),
        CheckConstraint(
            "decision IN ('AUTO_APPROVE', 'REVIEW_REQUIRED')",
            name="decision_valid",
        ),
        CheckConstraint("jsonb_typeof(issues) = 'array'", name="issues_array"),
        CheckConstraint(
            'issues <@ \'["MISSING_INVOICE_NUMBER", "MISSING_ISSUE_DATE", '
            '"MISSING_SUPPLIER_NAME", "MISSING_CURRENCY", '
            '"MISSING_TOTAL_AMOUNT", "NON_POSITIVE_TOTAL_AMOUNT"]\'::jsonb',
            name="issues_valid",
        ),
        CheckConstraint(
            "(decision = 'AUTO_APPROVE') = (jsonb_array_length(issues) = 0)",
            name="decision_matches_issues",
        ),
    )

    processing_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "processing_runs.id",
            name="fk_invoice_validations_processing_run_id_processing_runs",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    decision: Mapped[str] = mapped_column(String(32))
    issues: Mapped[list[str]] = mapped_column(JSONB)
    validated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
