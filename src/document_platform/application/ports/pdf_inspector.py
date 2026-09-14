"""PDF structural inspection contract."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PdfInspection:
    page_count: int


class InvalidPdf(ValueError):
    """Raised when content is not a structurally valid PDF."""


class EncryptedPdf(ValueError):
    """Raised when a PDF is encrypted or password protected."""


class PdfPageLimitExceeded(ValueError):
    def __init__(self, max_pages: int) -> None:
        super().__init__(f"PDF exceeds the {max_pages}-page limit")


class PdfInspector(Protocol):
    async def inspect(self, path: Path) -> PdfInspection: ...
