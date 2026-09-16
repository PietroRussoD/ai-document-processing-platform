"""Deterministic invoice extraction policy tests."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from document_platform.domain.processing import DeterministicInvoiceExtractionPolicy

AT = datetime(2026, 9, 16, 20, 0, tzinfo=UTC)
RUN_ID = UUID("c3c3c3c3-c3c3-43c3-83c3-c3c3c3c3c3c3")


def extract(text: str):
    return DeterministicInvoiceExtractionPolicy().extract(
        processing_run_id=RUN_ID,
        text=text,
        extracted_at=AT,
    )


def test_extracts_explicitly_labelled_english_invoice_fields() -> None:
    result = extract(
        """INVOICE
Invoice number: INV-42
Invoice date: 2026-09-16
Supplier: Acme Ltd
Total: EUR 1,234.50
"""
    )

    assert result.invoice_number == "INV-42"
    assert result.issue_date == date(2026, 9, 16)
    assert result.supplier_name == "Acme Ltd"
    assert result.currency == "EUR"
    assert result.total_amount == Decimal("1234.50")


def test_extracts_supported_italian_labels_and_currency_symbol() -> None:
    result = extract(
        """FATTURA
Fattura numero: 2026-17
Data: 16/09/2026
Fornitore: Acme S.r.l.
Totale: € 12,50
"""
    )

    assert result.invoice_number == "2026-17"
    assert result.issue_date == date(2026, 9, 16)
    assert result.supplier_name == "Acme S.r.l."
    assert result.currency == "EUR"
    assert result.total_amount == Decimal("12.50")


def test_leaves_unlabelled_or_invalid_values_missing() -> None:
    result = extract("Invoice INV-42 issued 2026-99-99 with 12.50 due")

    assert result.invoice_number is None
    assert result.issue_date is None
    assert result.supplier_name is None
    assert result.currency is None
    assert result.total_amount is None
