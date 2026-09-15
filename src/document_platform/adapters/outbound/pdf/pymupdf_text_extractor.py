"""Bounded embedded-text extraction using PyMuPDF."""

from typing import cast

import anyio
import pymupdf

from document_platform.application.ports import ExtractedPdfText, PdfTextLimitExceeded


class PyMuPdfTextExtractor:
    def __init__(self, *, max_pages: int, max_characters: int) -> None:
        if max_pages <= 0:
            raise ValueError("max_pages must be positive")
        if max_characters <= 0:
            raise ValueError("max_characters must be positive")
        self._max_pages = max_pages
        self._max_characters = max_characters

    async def extract(self, content: bytes) -> ExtractedPdfText:
        return await anyio.to_thread.run_sync(self._extract, content)

    def _extract(self, content: bytes) -> ExtractedPdfText:
        document = pymupdf.open(stream=content, filetype="pdf")
        with document:
            if document.is_encrypted:
                raise ValueError("encrypted PDFs are not supported")
            page_count = cast(int, document.page_count)  # pyright: ignore[reportUnknownMemberType]
            if not 1 <= page_count <= self._max_pages:
                raise ValueError("PDF page count is outside the supported limit")

            pages: list[str] = []
            character_count = 0
            for page in document:
                text = cast(str, page.get_text("text"))  # pyright: ignore[reportUnknownMemberType]
                character_count += len(text)
                if character_count > self._max_characters:
                    raise PdfTextLimitExceeded(self._max_characters)
                pages.append(text)

        extracted = "\f".join(pages)
        return ExtractedPdfText(
            text=extracted,
            page_count=page_count,
            character_count=len(extracted),
            non_whitespace_character_count=sum(not character.isspace() for character in extracted),
        )
