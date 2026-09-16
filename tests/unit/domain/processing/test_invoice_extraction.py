"""Structured invoice extraction domain-contract tests."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from document_platform.domain.processing import (
    InvalidInvoiceExtraction,
    InvoiceExtraction,
    InvoiceExtractionMethod,
)

AT = datetime(2026, 9, 16, 19, 0, tzinfo=UTC)
RUN_ID = UUID("b2b2b2b2-b2b2-42b2-82b2-b2b2b2b2b2b2")


def test_accepts_a_partial_invoice_result() -> None:
    extraction = InvoiceExtraction(
        processing_run_id=RUN_ID,
        method=InvoiceExtractionMethod.DETERMINISTIC_RULES,
        invoice_number="INV-42",
        issue_date=date(2026, 9, 16),
        supplier_name=None,
        currency="EUR",
        total_amount=Decimal("12.50"),
        extracted_at=AT,
    )

    assert extraction.invoice_number == "INV-42"
    assert extraction.total_amount == Decimal("12.50")


@pytest.mark.parametrize(
    ("processing_run_id", "invoice_number", "currency", "total_amount", "extracted_at"),
    [
        (UUID(int=0), "INV-42", "EUR", Decimal("12.50"), AT),
        (RUN_ID, "   ", "EUR", Decimal("12.50"), AT),
        (RUN_ID, "INV-42", "eur", Decimal("12.50"), AT),
        (RUN_ID, "INV-42", "EUR", Decimal("-12.50"), AT),
        (RUN_ID, "INV-42", "EUR", Decimal("12.12345"), AT),
        (RUN_ID, "INV-42", "EUR", Decimal("12.50"), datetime(2026, 9, 16, 19, 0)),
    ],
)
def test_rejects_invalid_invoice_result_invariants(
    processing_run_id: UUID,
    invoice_number: str,
    currency: str,
    total_amount: Decimal,
    extracted_at: datetime,
) -> None:
    with pytest.raises(InvalidInvoiceExtraction):
        InvoiceExtraction(
            processing_run_id=processing_run_id,
            method=InvoiceExtractionMethod.DETERMINISTIC_RULES,
            invoice_number=invoice_number,
            issue_date=date(2026, 9, 16),
            supplier_name="Acme S.r.l.",
            currency=currency,
            total_amount=total_amount,
            extracted_at=extracted_at,
        )
