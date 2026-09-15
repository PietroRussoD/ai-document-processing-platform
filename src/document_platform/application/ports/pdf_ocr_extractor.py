"""OCR contract for eligible PDF documents."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ExtractedOcrText:
    text: str
    page_count: int
    character_count: int
    non_whitespace_character_count: int


class OcrEngineUnavailable(RuntimeError):
    """Raised when the configured local OCR executable cannot be started."""


class OcrExtractionFailed(RuntimeError):
    """Raised when the OCR engine rejects or times out a page."""


class OcrTextLimitExceeded(ValueError):
    def __init__(self, max_characters: int) -> None:
        super().__init__(f"OCR extracted text exceeds the {max_characters}-character limit")


class PdfOcrExtractor(Protocol):
    async def extract(self, content: bytes) -> ExtractedOcrText: ...
