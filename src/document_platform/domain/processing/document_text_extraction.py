"""Immutable text extracted from one processing run."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from document_platform.domain.processing.embedded_text_quality import EmbeddedTextQuality


class TextExtractionMethod(StrEnum):
    PYMUPDF = "PYMUPDF"


class InvalidDocumentTextExtraction(ValueError):
    """Raised when extracted text metadata violates a domain invariant."""


@dataclass(frozen=True, slots=True)
class DocumentTextExtraction:
    processing_run_id: UUID
    method: TextExtractionMethod
    text: str
    page_count: int
    character_count: int
    non_whitespace_character_count: int
    quality: EmbeddedTextQuality
    extracted_at: datetime

    def __post_init__(self) -> None:
        if self.processing_run_id.int == 0:
            raise InvalidDocumentTextExtraction("processing_run_id must not be the nil UUID")
        if self.page_count <= 0:
            raise InvalidDocumentTextExtraction("page_count must be positive")
        if self.character_count != len(self.text):
            raise InvalidDocumentTextExtraction("character_count must equal text length")
        non_whitespace_count = sum(not character.isspace() for character in self.text)
        if self.non_whitespace_character_count != non_whitespace_count:
            raise InvalidDocumentTextExtraction(
                "non_whitespace_character_count must equal the text content"
            )
        if not _is_timezone_aware(self.extracted_at):
            raise InvalidDocumentTextExtraction("extracted_at must be timezone-aware")


def _is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None
