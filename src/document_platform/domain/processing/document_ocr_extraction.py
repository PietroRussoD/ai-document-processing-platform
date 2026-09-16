"""Immutable OCR text extracted for one processing run."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class OcrExtractionMethod(StrEnum):
    TESSERACT = "TESSERACT"


class InvalidDocumentOcrExtraction(ValueError):
    """Raised when OCR extraction metadata violates a domain invariant."""


@dataclass(frozen=True, slots=True)
class DocumentOcrExtraction:
    processing_run_id: UUID
    method: OcrExtractionMethod
    text: str
    page_count: int
    character_count: int
    non_whitespace_character_count: int
    extracted_at: datetime

    def __post_init__(self) -> None:
        if self.processing_run_id.int == 0:
            raise InvalidDocumentOcrExtraction("processing_run_id must not be the nil UUID")
        if self.page_count <= 0:
            raise InvalidDocumentOcrExtraction("page_count must be positive")
        if self.character_count != len(self.text):
            raise InvalidDocumentOcrExtraction("character_count must equal text length")
        if self.non_whitespace_character_count != sum(
            not character.isspace() for character in self.text
        ):
            raise InvalidDocumentOcrExtraction(
                "non_whitespace_character_count must equal the text content"
            )
        if self.extracted_at.tzinfo is None or self.extracted_at.utcoffset() is None:
            raise InvalidDocumentOcrExtraction("extracted_at must be timezone-aware")
