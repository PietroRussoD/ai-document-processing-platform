"""PyMuPDF-backed structural PDF inspection."""

from pathlib import Path
from typing import cast

import anyio
import pymupdf

from document_platform.application.ports import (
    EncryptedPdf,
    InvalidPdf,
    PdfInspection,
    PdfPageLimitExceeded,
)

PDF_SIGNATURE = b"%PDF-"


class PyMuPdfInspector:
    def __init__(self, max_pages: int) -> None:
        if max_pages <= 0:
            raise ValueError("max_pages must be positive")
        self._max_pages = max_pages

    async def inspect(self, path: Path) -> PdfInspection:
        return await anyio.to_thread.run_sync(self._inspect, path)

    def _inspect(self, path: Path) -> PdfInspection:
        with path.open("rb") as candidate:
            if candidate.read(len(PDF_SIGNATURE)) != PDF_SIGNATURE:
                raise InvalidPdf("content does not have a PDF signature")

        try:
            document = pymupdf.open(path)
        except (pymupdf.EmptyFileError, pymupdf.FileDataError) as error:
            raise InvalidPdf("content is not a structurally valid PDF") from error

        with document:
            if document.is_encrypted:
                raise EncryptedPdf("encrypted PDFs are not supported")

            page_count = cast(
                int,
                document.page_count,  # pyright: ignore[reportUnknownMemberType]
            )
            if page_count <= 0:
                raise InvalidPdf("PDF must contain at least one page")
            if page_count > self._max_pages:
                raise PdfPageLimitExceeded(self._max_pages)

            return PdfInspection(page_count=page_count)
