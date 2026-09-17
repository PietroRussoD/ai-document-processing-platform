"""Extract-invoice application tests."""

from datetime import UTC, datetime
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from document_platform.application.commands.extract_invoice import (
    ExtractInvoice,
    ExtractInvoiceHandler,
    InvoiceExtracted,
    InvoiceExtractionNotApplicable,
    InvoiceExtractionRequiresClassification,
    InvoiceExtractionRequiresSelectedText,
    InvoiceExtractionRequiresTextSelection,
)
from document_platform.application.ports import InvoiceExtractionAlreadyExists, UnitOfWork
from document_platform.domain.processing import (
    BusinessDocumentType,
    DeterministicInvoiceExtractionPolicy,
    DocumentClassification,
    DocumentClassificationReason,
    DocumentOcrExtraction,
    DocumentTextExtraction,
    DocumentTextSelection,
    EmbeddedTextQuality,
    InvoiceExtraction,
    OcrExtractionMethod,
    ProcessingTextSelectionReason,
    ProcessingTextSource,
    TextExtractionMethod,
)

AT = datetime(2026, 9, 16, 22, 0, tzinfo=UTC)
RUN_ID = UUID("f6f6f6f6-f6f6-46f6-86f6-f6f6f6f6f6f6")


class ValueRepository:
    def __init__(self, value: object | None = None) -> None:
        self.value = value
        self.added: list[object] = []

    async def get(self, processing_run_id: UUID) -> object | None:
        return self.value

    async def add(self, value: object) -> None:
        self.value = value
        self.added.append(value)


class RecordingUnitOfWork:
    def __init__(self) -> None:
        self.invoice_extractions = ValueRepository()
        self.document_classifications = ValueRepository(
            DocumentClassification(
                processing_run_id=RUN_ID,
                document_type=BusinessDocumentType.INVOICE,
                reason=DocumentClassificationReason.KEYWORD_MATCHED,
                classified_at=AT,
            )
        )
        self.document_text_selections = ValueRepository(
            DocumentTextSelection(
                processing_run_id=RUN_ID,
                source=ProcessingTextSource.EMBEDDED,
                reason=ProcessingTextSelectionReason.EMBEDDED_SUFFICIENT,
                selected_at=AT,
            )
        )
        text = "Invoice number: INV-42\nTotal: EUR 12.50"
        self.document_text_extractions = ValueRepository(
            DocumentTextExtraction(
                processing_run_id=RUN_ID,
                method=TextExtractionMethod.PYMUPDF,
                text=text,
                page_count=1,
                character_count=len(text),
                non_whitespace_character_count=sum(not character.isspace() for character in text),
                quality=EmbeddedTextQuality.SUFFICIENT,
                extracted_at=AT,
            )
        )
        self.document_ocr_extractions = ValueRepository()
        self.commit_count = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.commit_count += 1


class DuplicateInvoiceExtractionRepository(ValueRepository):
    async def add(self, value: object) -> None:
        raise InvoiceExtractionAlreadyExists(RUN_ID)


def handler(unit_of_work: RecordingUnitOfWork) -> ExtractInvoiceHandler:
    return ExtractInvoiceHandler(
        unit_of_work_factory=lambda: cast(UnitOfWork, unit_of_work),
        extraction_policy=DeterministicInvoiceExtractionPolicy(),
        clock=lambda: AT,
    )


@pytest.mark.anyio
async def test_extracts_and_persists_the_selected_invoice_text() -> None:
    unit_of_work = RecordingUnitOfWork()

    result = await handler(unit_of_work)(ExtractInvoice(RUN_ID))

    assert result == InvoiceExtracted(RUN_ID, replayed=False)
    extraction = cast(InvoiceExtraction, unit_of_work.invoice_extractions.added[0])
    assert extraction.invoice_number == "INV-42"
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_replay_reuses_the_persisted_invoice_extraction() -> None:
    unit_of_work = RecordingUnitOfWork()
    command = ExtractInvoice(RUN_ID)

    await handler(unit_of_work)(command)
    replay = await handler(unit_of_work)(command)

    assert replay == InvoiceExtracted(RUN_ID, replayed=True)
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_concurrent_persist_returns_a_replay_result() -> None:
    unit_of_work = RecordingUnitOfWork()
    unit_of_work.invoice_extractions = DuplicateInvoiceExtractionRepository()

    result = await handler(unit_of_work)(ExtractInvoice(RUN_ID))

    assert result == InvoiceExtracted(RUN_ID, replayed=True)
    assert unit_of_work.commit_count == 0


@pytest.mark.anyio
async def test_requires_a_persisted_classification() -> None:
    unit_of_work = RecordingUnitOfWork()
    unit_of_work.document_classifications.value = None

    with pytest.raises(InvoiceExtractionRequiresClassification):
        await handler(unit_of_work)(ExtractInvoice(RUN_ID))


@pytest.mark.anyio
async def test_rejects_a_non_invoice_classification() -> None:
    unit_of_work = RecordingUnitOfWork()
    unit_of_work.document_classifications.value = DocumentClassification(
        processing_run_id=RUN_ID,
        document_type=BusinessDocumentType.PURCHASE_ORDER,
        reason=DocumentClassificationReason.KEYWORD_MATCHED,
        classified_at=AT,
    )

    with pytest.raises(InvoiceExtractionNotApplicable):
        await handler(unit_of_work)(ExtractInvoice(RUN_ID))


@pytest.mark.anyio
async def test_requires_a_persisted_text_selection() -> None:
    unit_of_work = RecordingUnitOfWork()
    unit_of_work.document_text_selections.value = None

    with pytest.raises(InvoiceExtractionRequiresTextSelection):
        await handler(unit_of_work)(ExtractInvoice(RUN_ID))


@pytest.mark.anyio
async def test_requires_the_selected_text_to_exist() -> None:
    unit_of_work = RecordingUnitOfWork()
    unit_of_work.document_text_extractions.value = None

    with pytest.raises(InvoiceExtractionRequiresSelectedText):
        await handler(unit_of_work)(ExtractInvoice(RUN_ID))


@pytest.mark.anyio
async def test_extracts_the_selected_ocr_text() -> None:
    unit_of_work = RecordingUnitOfWork()
    unit_of_work.document_text_selections.value = DocumentTextSelection(
        processing_run_id=RUN_ID,
        source=ProcessingTextSource.OCR,
        reason=ProcessingTextSelectionReason.OCR_HAS_MORE_TEXT,
        selected_at=AT,
    )
    text = "Invoice number: OCR-42\nTotal: EUR 99.00"
    unit_of_work.document_ocr_extractions.value = DocumentOcrExtraction(
        processing_run_id=RUN_ID,
        method=OcrExtractionMethod.TESSERACT,
        text=text,
        page_count=1,
        character_count=len(text),
        non_whitespace_character_count=sum(not character.isspace() for character in text),
        extracted_at=AT,
    )

    await handler(unit_of_work)(ExtractInvoice(RUN_ID))

    extraction = cast(InvoiceExtraction, unit_of_work.invoice_extractions.added[0])
    assert extraction.invoice_number == "OCR-42"
