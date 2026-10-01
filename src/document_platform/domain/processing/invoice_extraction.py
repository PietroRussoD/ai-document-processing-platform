"""Immutable structured invoice extraction result."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from document_platform.domain.processing.currency_code import is_iso_currency_code


class InvoiceExtractionMethod(StrEnum):
    DETERMINISTIC_RULES = "DETERMINISTIC_RULES"
    OLLAMA = "OLLAMA"


class InvalidInvoiceExtraction(ValueError):
    """Raised when structured invoice data violates the public contract."""


@dataclass(frozen=True, slots=True)
class InvoiceExtraction:
    processing_run_id: UUID
    method: InvoiceExtractionMethod
    invoice_number: str | None
    issue_date: date | None
    supplier_name: str | None
    currency: str | None
    total_amount: Decimal | None
    extracted_at: datetime

    def __post_init__(self) -> None:
        if self.processing_run_id.int == 0:
            raise InvalidInvoiceExtraction("processing_run_id must not be the nil UUID")
        for field_name, value in (
            ("invoice_number", self.invoice_number),
            ("supplier_name", self.supplier_name),
        ):
            if value is not None and not value.strip():
                raise InvalidInvoiceExtraction(f"{field_name} must not be blank")
        if self.currency is not None and not is_iso_currency_code(self.currency):
            raise InvalidInvoiceExtraction("currency must be an ISO 4217 alpha code")
        if self.total_amount is not None:
            if not self.total_amount.is_finite():
                raise InvalidInvoiceExtraction("total_amount must be finite")
            if self.total_amount < Decimal("0"):
                raise InvalidInvoiceExtraction("total_amount must not be negative")
            exponent = self.total_amount.as_tuple().exponent
            if not isinstance(exponent, int) or -exponent > 4:
                raise InvalidInvoiceExtraction("total_amount must have at most four decimal places")
        if not _is_timezone_aware(self.extracted_at):
            raise InvalidInvoiceExtraction("extracted_at must be timezone-aware")


def _is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None
