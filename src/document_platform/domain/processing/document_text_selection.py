"""Immutable decision selecting canonical text for one processing run."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from document_platform.domain.processing.document_ocr_extraction import DocumentOcrExtraction
from document_platform.domain.processing.document_text_extraction import DocumentTextExtraction
from document_platform.domain.processing.embedded_text_quality import EmbeddedTextQuality


class ProcessingTextSource(StrEnum):
    EMBEDDED = "EMBEDDED"
    OCR = "OCR"


class ProcessingTextSelectionReason(StrEnum):
    EMBEDDED_SUFFICIENT = "EMBEDDED_SUFFICIENT"
    OCR_HAS_MORE_TEXT = "OCR_HAS_MORE_TEXT"
    EMBEDDED_NOT_WORSE = "EMBEDDED_NOT_WORSE"


class InvalidDocumentTextSelection(ValueError):
    """Raised when a text-selection record violates a domain invariant."""


@dataclass(frozen=True, slots=True)
class DocumentTextSelection:
    processing_run_id: UUID
    source: ProcessingTextSource
    reason: ProcessingTextSelectionReason
    selected_at: datetime

    def __post_init__(self) -> None:
        if self.processing_run_id.int == 0:
            raise InvalidDocumentTextSelection("processing_run_id must not be the nil UUID")
        if self.selected_at.tzinfo is None or self.selected_at.utcoffset() is None:
            raise InvalidDocumentTextSelection("selected_at must be timezone-aware")
        if (
            self.reason is ProcessingTextSelectionReason.EMBEDDED_SUFFICIENT
            and self.source is not ProcessingTextSource.EMBEDDED
        ):
            raise InvalidDocumentTextSelection(
                "an embedded-sufficient selection must use embedded text"
            )
        if (
            self.reason is ProcessingTextSelectionReason.OCR_HAS_MORE_TEXT
            and self.source is not ProcessingTextSource.OCR
        ):
            raise InvalidDocumentTextSelection("an OCR-improved selection must use OCR text")
        if (
            self.reason is ProcessingTextSelectionReason.EMBEDDED_NOT_WORSE
            and self.source is not ProcessingTextSource.EMBEDDED
        ):
            raise InvalidDocumentTextSelection(
                "an embedded-not-worse selection must use embedded text"
            )


class ProcessingTextSelectionPolicy:
    def select(
        self,
        *,
        embedded: DocumentTextExtraction,
        ocr: DocumentOcrExtraction | None,
        selected_at: datetime,
    ) -> DocumentTextSelection:
        if embedded.quality is EmbeddedTextQuality.SUFFICIENT:
            return DocumentTextSelection(
                processing_run_id=embedded.processing_run_id,
                source=ProcessingTextSource.EMBEDDED,
                reason=ProcessingTextSelectionReason.EMBEDDED_SUFFICIENT,
                selected_at=selected_at,
            )
        if ocr is None:
            raise InvalidDocumentTextSelection(
                "OCR result is required when embedded text needs OCR"
            )
        if ocr.processing_run_id != embedded.processing_run_id:
            raise InvalidDocumentTextSelection("OCR result belongs to a different processing run")
        if ocr.non_whitespace_character_count > embedded.non_whitespace_character_count:
            return DocumentTextSelection(
                processing_run_id=embedded.processing_run_id,
                source=ProcessingTextSource.OCR,
                reason=ProcessingTextSelectionReason.OCR_HAS_MORE_TEXT,
                selected_at=selected_at,
            )
        return DocumentTextSelection(
            processing_run_id=embedded.processing_run_id,
            source=ProcessingTextSource.EMBEDDED,
            reason=ProcessingTextSelectionReason.EMBEDDED_NOT_WORSE,
            selected_at=selected_at,
        )
