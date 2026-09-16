"""Canonical processing-text selection policy tests."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest

from document_platform.domain.processing import (
    DocumentOcrExtraction,
    DocumentTextExtraction,
    EmbeddedTextQuality,
    InvalidDocumentTextSelection,
    OcrExtractionMethod,
    ProcessingTextSelectionPolicy,
    ProcessingTextSelectionReason,
    ProcessingTextSource,
    TextExtractionMethod,
)

RUN_ID = UUID("91919191-9191-4191-8191-919191919191")
AT = datetime(2026, 9, 16, 10, 0, tzinfo=UTC)


def embedded(*, quality: EmbeddedTextQuality, text: str = "short") -> DocumentTextExtraction:
    return DocumentTextExtraction(
        processing_run_id=RUN_ID,
        method=TextExtractionMethod.PYMUPDF,
        text=text,
        page_count=1,
        character_count=len(text),
        non_whitespace_character_count=sum(not character.isspace() for character in text),
        quality=quality,
        extracted_at=AT,
    )


def ocr(text: str) -> DocumentOcrExtraction:
    return DocumentOcrExtraction(
        processing_run_id=RUN_ID,
        method=OcrExtractionMethod.TESSERACT,
        text=text,
        page_count=1,
        character_count=len(text),
        non_whitespace_character_count=sum(not character.isspace() for character in text),
        extracted_at=AT,
    )


def test_selects_sufficient_embedded_text_without_ocr() -> None:
    selection = ProcessingTextSelectionPolicy().select(
        embedded=embedded(quality=EmbeddedTextQuality.SUFFICIENT),
        ocr=None,
        selected_at=AT,
    )

    assert selection.source is ProcessingTextSource.EMBEDDED
    assert selection.reason is ProcessingTextSelectionReason.EMBEDDED_SUFFICIENT


def test_selects_ocr_only_when_it_has_more_usable_text() -> None:
    selection = ProcessingTextSelectionPolicy().select(
        embedded=embedded(quality=EmbeddedTextQuality.OCR_RECOMMENDED, text="bad"),
        ocr=ocr("invoice total 42"),
        selected_at=AT,
    )

    assert selection.source is ProcessingTextSource.OCR
    assert selection.reason is ProcessingTextSelectionReason.OCR_HAS_MORE_TEXT


def test_keeps_embedded_text_when_ocr_is_not_better() -> None:
    selection = ProcessingTextSelectionPolicy().select(
        embedded=embedded(quality=EmbeddedTextQuality.OCR_RECOMMENDED, text="short"),
        ocr=ocr("bad"),
        selected_at=AT,
    )

    assert selection.source is ProcessingTextSource.EMBEDDED
    assert selection.reason is ProcessingTextSelectionReason.EMBEDDED_NOT_WORSE


def test_rejects_a_missing_ocr_result_when_the_policy_requires_it() -> None:
    with pytest.raises(InvalidDocumentTextSelection, match="OCR result is required"):
        ProcessingTextSelectionPolicy().select(
            embedded=embedded(quality=EmbeddedTextQuality.OCR_RECOMMENDED),
            ocr=None,
            selected_at=AT,
        )


def test_rejects_an_ocr_result_from_a_different_run() -> None:
    with pytest.raises(InvalidDocumentTextSelection, match="different processing run"):
        ProcessingTextSelectionPolicy().select(
            embedded=embedded(quality=EmbeddedTextQuality.OCR_RECOMMENDED),
            ocr=replace(
                ocr("invoice"),
                processing_run_id=UUID("96969696-9696-4696-8696-969696969696"),
            ),
            selected_at=AT,
        )
