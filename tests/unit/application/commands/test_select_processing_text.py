"""Canonical processing-text selection application tests."""

from datetime import UTC, datetime
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from document_platform.application.commands import (
    ProcessingTextSelected,
    SelectProcessingText,
    SelectProcessingTextHandler,
)
from document_platform.application.ports import UnitOfWork
from document_platform.domain.processing import (
    DocumentOcrExtraction,
    DocumentTextExtraction,
    DocumentTextSelection,
    EmbeddedTextQuality,
    OcrExtractionMethod,
    ProcessingTextSelectionPolicy,
    ProcessingTextSource,
    TextExtractionMethod,
)

AT = datetime(2026, 9, 16, 10, 0, tzinfo=UTC)
RUN_ID = UUID("93939393-9393-4393-8393-939393939393")


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
    def __init__(
        self,
        *,
        embedded: DocumentTextExtraction,
        ocr: DocumentOcrExtraction | None,
    ) -> None:
        self.document_text_extractions = ValueRepository(embedded)
        self.document_ocr_extractions = ValueRepository(ocr)
        self.document_text_selections = ValueRepository()
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


def embedded(quality: EmbeddedTextQuality) -> DocumentTextExtraction:
    return DocumentTextExtraction(
        processing_run_id=RUN_ID,
        method=TextExtractionMethod.PYMUPDF,
        text="short",
        page_count=1,
        character_count=5,
        non_whitespace_character_count=5,
        quality=quality,
        extracted_at=AT,
    )


def ocr() -> DocumentOcrExtraction:
    return DocumentOcrExtraction(
        processing_run_id=RUN_ID,
        method=OcrExtractionMethod.TESSERACT,
        text="invoice total 42",
        page_count=1,
        character_count=16,
        non_whitespace_character_count=14,
        extracted_at=AT,
    )


def handler(unit_of_work: RecordingUnitOfWork) -> SelectProcessingTextHandler:
    return SelectProcessingTextHandler(
        unit_of_work_factory=lambda: cast(UnitOfWork, unit_of_work),
        selection_policy=ProcessingTextSelectionPolicy(),
        clock=lambda: AT,
    )


@pytest.mark.anyio
async def test_selects_and_persists_the_better_ocr_result() -> None:
    unit_of_work = RecordingUnitOfWork(
        embedded=embedded(EmbeddedTextQuality.OCR_RECOMMENDED),
        ocr=ocr(),
    )

    result = await handler(unit_of_work)(SelectProcessingText(RUN_ID))

    assert result == ProcessingTextSelected(RUN_ID, replayed=False)
    selection = cast(DocumentTextSelection, unit_of_work.document_text_selections.added[0])
    assert selection.source is ProcessingTextSource.OCR
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_replay_reuses_the_persisted_selection() -> None:
    unit_of_work = RecordingUnitOfWork(
        embedded=embedded(EmbeddedTextQuality.SUFFICIENT),
        ocr=None,
    )
    command = SelectProcessingText(RUN_ID)

    await handler(unit_of_work)(command)
    replay = await handler(unit_of_work)(command)

    assert replay == ProcessingTextSelected(RUN_ID, replayed=True)
    assert unit_of_work.commit_count == 1
