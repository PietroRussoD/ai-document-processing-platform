"""Document HTTP response mapping tests."""

from datetime import UTC, date, datetime
from decimal import Decimal

from document_platform.adapters.inbound.http.documents import (
    InvoiceExtractionMetadataResponse,
)
from document_platform.application.ports import InvoiceExtractionMetadataView
from document_platform.domain.processing import InvoiceExtractionMethod


def test_serializes_a_decimal_invoice_total_as_a_json_safe_string() -> None:
    response = InvoiceExtractionMetadataResponse.model_validate(
        InvoiceExtractionMetadataView(
            method=InvoiceExtractionMethod.DETERMINISTIC_RULES,
            invoice_number="INV-42",
            issue_date=date(2026, 9, 17),
            supplier_name="Acme Ltd",
            currency="EUR",
            total_amount=Decimal("39.9800"),
            extracted_at=datetime(2026, 9, 17, tzinfo=UTC),
        )
    )

    assert response.total_amount == "39.9800"
