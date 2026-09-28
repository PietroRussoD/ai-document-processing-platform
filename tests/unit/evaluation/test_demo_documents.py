"""Expected behavior for the versioned local demo PDFs."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from shutil import which
from typing import cast
from uuid import UUID

import pymupdf
import pytest

from document_platform.adapters.outbound.ocr import TesseractPdfOcrExtractor
from document_platform.adapters.outbound.pdf import PyMuPdfTextExtractor
from document_platform.domain.processing import (
    BusinessDocumentType,
    DeterministicInvoiceExtractionPolicy,
    DocumentClassificationPolicy,
    DocumentClassificationReason,
    InvoiceValidationDecision,
    InvoiceValidationIssue,
    InvoiceValidationPolicy,
)

FIXTURES = Path(__file__).resolve().parents[3] / "examples/documents"
RUN_ID = UUID("d4d4d4d4-d4d4-44d4-84d4-d4d4d4d4d4d4")
AT = datetime(2026, 9, 27, tzinfo=UTC)


def _document_text(filename: str) -> str:
    document = pymupdf.open(FIXTURES / filename)
    try:
        return "\n".join(
            cast(str, page.get_text("text"))  # pyright: ignore[reportUnknownMemberType]
            for page in document
        )
    finally:
        document.close()


def _classification(text: str):
    return DocumentClassificationPolicy().classify(
        processing_run_id=RUN_ID,
        text=text,
        classified_at=AT,
    )


def test_digital_invoice_requires_review_for_an_unsupported_currency() -> None:
    text = _document_text("invoice-digital.pdf")
    classification = _classification(text)
    extraction = DeterministicInvoiceExtractionPolicy().extract(
        processing_run_id=RUN_ID,
        text=text,
        extracted_at=AT,
    )

    assert classification.document_type is BusinessDocumentType.INVOICE
    assert classification.reason is DocumentClassificationReason.KEYWORD_MATCHED
    assert extraction.invoice_number == "DEMO-INV-1001"
    assert extraction.supplier_name == "Northstar Office Supplies Ltd"
    assert extraction.issue_date == date(2026, 9, 15)
    assert extraction.currency is None
    assert extraction.total_amount is None
    validation = InvoiceValidationPolicy().validate(extraction=extraction, validated_at=AT)
    assert validation.decision is InvoiceValidationDecision.REVIEW_REQUIRED
    assert validation.issues == (
        InvoiceValidationIssue.MISSING_CURRENCY,
        InvoiceValidationIssue.MISSING_TOTAL_AMOUNT,
    )


def test_scanned_invoice_has_no_embedded_text_layer() -> None:
    assert _document_text("invoice-scanned.pdf").strip() == ""


@pytest.mark.skipif(which("tesseract") is None, reason="Tesseract is not installed")
@pytest.mark.anyio
async def test_scanned_invoice_is_classified_and_extracted_through_ocr() -> None:
    content = (FIXTURES / "invoice-scanned.pdf").read_bytes()
    result = await TesseractPdfOcrExtractor(
        command="tesseract",
        language="eng",
        max_pages=1,
        max_characters=10_000,
        raster_dpi=200,
        page_timeout_seconds=10,
    ).extract(content)
    classification = _classification(result.text)
    extraction = DeterministicInvoiceExtractionPolicy().extract(
        processing_run_id=RUN_ID,
        text=result.text,
        extracted_at=AT,
    )

    assert classification.document_type is BusinessDocumentType.INVOICE
    assert extraction.invoice_number == "DEMO-INV-1002"
    assert extraction.supplier_name == "Cedar Lane Technology Ltd"
    assert extraction.issue_date is None
    assert extraction.currency == "EUR"
    assert extraction.total_amount == Decimal("875.25")


def test_unrelated_report_is_unsupported_by_document_classification() -> None:
    classification = _classification(_document_text("equipment-report.pdf"))

    assert classification.document_type is BusinessDocumentType.UNKNOWN
    assert classification.reason is DocumentClassificationReason.NO_MATCH


@pytest.mark.anyio
async def test_digital_fixture_uses_embedded_text_extractor() -> None:
    result = await PyMuPdfTextExtractor(max_pages=1, max_characters=10_000).extract(
        (FIXTURES / "invoice-digital.pdf").read_bytes()
    )

    assert result.non_whitespace_character_count > 100
    assert "DEMO-INV-1001" in result.text
