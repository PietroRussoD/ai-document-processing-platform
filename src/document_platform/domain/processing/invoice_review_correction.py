"""Immutable operator corrections for an extracted invoice."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class InvoiceReviewField(StrEnum):
    INVOICE_NUMBER = "INVOICE_NUMBER"
    ISSUE_DATE = "ISSUE_DATE"
    SUPPLIER_NAME = "SUPPLIER_NAME"
    CURRENCY = "CURRENCY"
    TOTAL_AMOUNT = "TOTAL_AMOUNT"


class InvoiceReviewCorrectionSource(StrEnum):
    MANUAL = "MANUAL"
    AI_PROPOSAL = "AI_PROPOSAL"


type InvoiceReviewFieldValue = str | date | Decimal


class InvalidInvoiceReviewCorrection(ValueError):
    """Raised when an operator correction violates invoice field invariants."""


@dataclass(frozen=True, slots=True)
class InvoiceReviewFieldCorrection:
    field: InvoiceReviewField
    corrected_value: InvoiceReviewFieldValue
    source: InvoiceReviewCorrectionSource = InvoiceReviewCorrectionSource.MANUAL

    def __post_init__(self) -> None:
        _validate_corrected_value(field=self.field, value=self.corrected_value)


@dataclass(frozen=True, slots=True)
class InvoiceReviewCorrection:
    processing_run_id: UUID
    corrections: tuple[InvoiceReviewFieldCorrection, ...]
    corrected_at: datetime

    def __post_init__(self) -> None:
        if self.processing_run_id.int == 0:
            raise InvalidInvoiceReviewCorrection("processing_run_id must not be the nil UUID")
        if type(self.corrections) is not tuple or not self.corrections:
            raise InvalidInvoiceReviewCorrection("corrections must be a non-empty tuple")
        fields = tuple(correction.field for correction in self.corrections)
        if len(set(fields)) != len(fields):
            raise InvalidInvoiceReviewCorrection("corrections must not contain duplicate fields")
        if not _is_timezone_aware(self.corrected_at):
            raise InvalidInvoiceReviewCorrection("corrected_at must be timezone-aware")


def _validate_corrected_value(*, field: InvoiceReviewField, value: InvoiceReviewFieldValue) -> None:
    if field in (InvoiceReviewField.INVOICE_NUMBER, InvoiceReviewField.SUPPLIER_NAME):
        if not isinstance(value, str) or not value.strip():
            raise InvalidInvoiceReviewCorrection(f"{field} must be a non-blank string")
        return
    if field is InvoiceReviewField.CURRENCY:
        if not isinstance(value, str) or not _is_iso_currency_code(value):
            raise InvalidInvoiceReviewCorrection(
                "CURRENCY must be an uppercase ISO 4217 alpha code"
            )
        return
    if field is InvoiceReviewField.ISSUE_DATE:
        if not isinstance(value, date) or isinstance(value, datetime):
            raise InvalidInvoiceReviewCorrection("ISSUE_DATE must be a date")
        return
    if field is InvoiceReviewField.TOTAL_AMOUNT:
        if not isinstance(value, Decimal):
            raise InvalidInvoiceReviewCorrection("TOTAL_AMOUNT must be a Decimal")
        if not value.is_finite() or value <= Decimal("0"):
            raise InvalidInvoiceReviewCorrection("TOTAL_AMOUNT must be finite and positive")
        exponent = value.as_tuple().exponent
        if not isinstance(exponent, int) or -exponent > 4:
            raise InvalidInvoiceReviewCorrection(
                "TOTAL_AMOUNT must have at most four decimal places"
            )
        return
    raise InvalidInvoiceReviewCorrection(f"unsupported review field: {field}")


def _is_iso_currency_code(value: str) -> bool:
    return len(value) == 3 and value.isascii() and value.isalpha() and value.isupper()


def _is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None
