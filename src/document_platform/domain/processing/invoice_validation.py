"""Deterministic completeness validation for extracted invoices."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from document_platform.domain.processing.invoice_extraction import InvoiceExtraction


class InvoiceValidationDecision(StrEnum):
    AUTO_APPROVE = "AUTO_APPROVE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class InvoiceValidationIssue(StrEnum):
    MISSING_INVOICE_NUMBER = "MISSING_INVOICE_NUMBER"
    MISSING_ISSUE_DATE = "MISSING_ISSUE_DATE"
    MISSING_SUPPLIER_NAME = "MISSING_SUPPLIER_NAME"
    MISSING_CURRENCY = "MISSING_CURRENCY"
    MISSING_TOTAL_AMOUNT = "MISSING_TOTAL_AMOUNT"
    NON_POSITIVE_TOTAL_AMOUNT = "NON_POSITIVE_TOTAL_AMOUNT"


class InvalidInvoiceValidation(ValueError):
    """Raised when an invoice-validation result violates its invariants."""


@dataclass(frozen=True, slots=True)
class InvoiceValidation:
    processing_run_id: UUID
    decision: InvoiceValidationDecision
    issues: tuple[InvoiceValidationIssue, ...]
    validated_at: datetime

    def __post_init__(self) -> None:
        if self.processing_run_id.int == 0:
            raise InvalidInvoiceValidation("processing_run_id must not be the nil UUID")
        if len(set(self.issues)) != len(self.issues):
            raise InvalidInvoiceValidation("issues must not contain duplicates")
        if (self.decision is InvoiceValidationDecision.AUTO_APPROVE) != (not self.issues):
            raise InvalidInvoiceValidation(
                "auto approval requires no issues and review requires at least one issue"
            )
        if self.validated_at.tzinfo is None or self.validated_at.utcoffset() is None:
            raise InvalidInvoiceValidation("validated_at must be timezone-aware")


class InvoiceValidationPolicy:
    def validate(
        self,
        *,
        extraction: InvoiceExtraction,
        validated_at: datetime,
    ) -> InvoiceValidation:
        issues = tuple(
            issue
            for condition, issue in (
                (
                    extraction.invoice_number is None,
                    InvoiceValidationIssue.MISSING_INVOICE_NUMBER,
                ),
                (extraction.issue_date is None, InvoiceValidationIssue.MISSING_ISSUE_DATE),
                (
                    extraction.supplier_name is None,
                    InvoiceValidationIssue.MISSING_SUPPLIER_NAME,
                ),
                (extraction.currency is None, InvoiceValidationIssue.MISSING_CURRENCY),
                (
                    extraction.total_amount is None,
                    InvoiceValidationIssue.MISSING_TOTAL_AMOUNT,
                ),
                (
                    extraction.total_amount is not None and extraction.total_amount <= Decimal("0"),
                    InvoiceValidationIssue.NON_POSITIVE_TOTAL_AMOUNT,
                ),
            )
            if condition
        )
        return InvoiceValidation(
            processing_run_id=extraction.processing_run_id,
            decision=(
                InvoiceValidationDecision.AUTO_APPROVE
                if not issues
                else InvoiceValidationDecision.REVIEW_REQUIRED
            ),
            issues=issues,
            validated_at=validated_at,
        )
