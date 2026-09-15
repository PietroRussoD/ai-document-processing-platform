"""Embedded-text extraction contract for eligible PDFs."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ExtractedPdfText:
    text: str
    page_count: int
    character_count: int
    non_whitespace_character_count: int


class PdfTextLimitExceeded(ValueError):
    def __init__(self, max_characters: int) -> None:
        super().__init__(f"PDF extracted text exceeds the {max_characters}-character limit")


class PdfTextExtractor(Protocol):
    async def extract(self, content: bytes) -> ExtractedPdfText: ...
