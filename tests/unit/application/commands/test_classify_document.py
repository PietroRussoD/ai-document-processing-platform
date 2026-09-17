"""Document-classification application tests."""

from datetime import UTC, datetime
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from document_platform.application.commands import (
    ClassificationRequiresSelectedText,
    ClassificationRequiresTextSelection,
    ClassifyDocument,
    ClassifyDocumentHandler,
    DocumentClassified,
)
from document_platform.application.ports import UnitOfWork
from document_platform.domain.processing import (
    BusinessDocumentType,
    DocumentClassification,
    DocumentClassificationPolicy,
    DocumentOcrExtraction,
    DocumentTextExtraction,
    DocumentTextSelection,
    EmbeddedTextQuality,
    OcrExtractionMethod,
    ProcessingTextSelectionReason,
    ProcessingTextSource,
    TextExtractionMethod,
)

AT = datetime(2026, 9, 16, 11, 0, tzinfo=UTC)
RUN_ID = UUID("a3a3a3a3-a3a3-43a3-83a3-a3a3a3a3a3a3")


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
        self.document_classifications = ValueRepository()
        self.document_text_selections = ValueRepository(
            DocumentTextSelection(
                processing_run_id=RUN_ID,
                source=ProcessingTextSource.EMBEDDED,
                reason=ProcessingTextSelectionReason.EMBEDDED_SUFFICIENT,
                selected_at=AT,
            )
        )
        self.document_text_extractions = ValueRepository(
            DocumentTextExtraction(
                processing_run_id=RUN_ID,
                method=TextExtractionMethod.PYMUPDF,
                text="Invoice number 42",
                page_count=1,
                character_count=17,
                non_whitespace_character_count=15,
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


def handler(unit_of_work: RecordingUnitOfWork) -> ClassifyDocumentHandler:
    return ClassifyDocumentHandler(
        unit_of_work_factory=lambda: cast(UnitOfWork, unit_of_work),
        classification_policy=DocumentClassificationPolicy(),
        clock=lambda: AT,
    )


@pytest.mark.anyio
async def test_classifies_and_persists_the_selected_text() -> None:
    unit_of_work = RecordingUnitOfWork()

    result = await handler(unit_of_work)(ClassifyDocument(RUN_ID))

    assert result == DocumentClassified(
        RUN_ID,
        replayed=False,
        document_type=BusinessDocumentType.INVOICE,
    )
    classification = cast(DocumentClassification, unit_of_work.document_classifications.added[0])
    assert classification.document_type is BusinessDocumentType.INVOICE
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_replay_reuses_the_persisted_classification() -> None:
    unit_of_work = RecordingUnitOfWork()
    command = ClassifyDocument(RUN_ID)

    await handler(unit_of_work)(command)
    replay = await handler(unit_of_work)(command)

    assert replay == DocumentClassified(
        RUN_ID,
        replayed=True,
        document_type=BusinessDocumentType.INVOICE,
    )
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_classifies_the_persisted_ocr_text_when_it_was_selected() -> None:
    unit_of_work = RecordingUnitOfWork()
    unit_of_work.document_text_selections.value = DocumentTextSelection(
        processing_run_id=RUN_ID,
        source=ProcessingTextSource.OCR,
        reason=ProcessingTextSelectionReason.OCR_HAS_MORE_TEXT,
        selected_at=AT,
    )
    unit_of_work.document_ocr_extractions.value = DocumentOcrExtraction(
        processing_run_id=RUN_ID,
        method=OcrExtractionMethod.TESSERACT,
        text="Credit note 42",
        page_count=1,
        character_count=14,
        non_whitespace_character_count=12,
        extracted_at=AT,
    )

    await handler(unit_of_work)(ClassifyDocument(RUN_ID))

    classification = unit_of_work.document_classifications.added[0]
    assert isinstance(classification, DocumentClassification)
    assert classification.document_type is BusinessDocumentType.CREDIT_NOTE


@pytest.mark.anyio
async def test_requires_a_persisted_text_selection() -> None:
    unit_of_work = RecordingUnitOfWork()
    unit_of_work.document_text_selections.value = None

    with pytest.raises(ClassificationRequiresTextSelection):
        await handler(unit_of_work)(ClassifyDocument(RUN_ID))


@pytest.mark.anyio
async def test_requires_the_selected_text_to_exist() -> None:
    unit_of_work = RecordingUnitOfWork()
    unit_of_work.document_text_extractions.value = None

    with pytest.raises(ClassificationRequiresSelectedText):
        await handler(unit_of_work)(ClassifyDocument(RUN_ID))
