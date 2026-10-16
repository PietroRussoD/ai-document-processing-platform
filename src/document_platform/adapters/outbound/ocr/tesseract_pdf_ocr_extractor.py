"""Bounded local Tesseract OCR for eligible PDFs."""

import asyncio
from asyncio.subprocess import PIPE
from typing import cast

import anyio
import pymupdf

from document_platform.application.ports import (
    ExtractedOcrText,
    OcrEngineUnavailable,
    OcrExtractionFailed,
    OcrTextLimitExceeded,
)


class TesseractPdfOcrExtractor:
    def __init__(
        self,
        *,
        command: str,
        language: str,
        max_pages: int,
        max_characters: int,
        raster_dpi: int,
        max_page_pixels: int,
        page_timeout_seconds: float,
    ) -> None:
        if not command.strip():
            raise ValueError("command must not be blank")
        if not language.strip():
            raise ValueError("language must not be blank")
        if max_pages <= 0:
            raise ValueError("max_pages must be positive")
        if max_characters <= 0:
            raise ValueError("max_characters must be positive")
        if raster_dpi < 72:
            raise ValueError("raster_dpi must be at least 72")
        if max_page_pixels <= 0:
            raise ValueError("max_page_pixels must be positive")
        if page_timeout_seconds <= 0:
            raise ValueError("page_timeout_seconds must be positive")
        self._command = command
        self._language = language
        self._max_pages = max_pages
        self._max_characters = max_characters
        self._raster_dpi = raster_dpi
        self._max_page_pixels = max_page_pixels
        self._page_timeout_seconds = page_timeout_seconds

    async def extract(self, content: bytes) -> ExtractedOcrText:
        # Keep the document on one worker thread while OCR runs on the event loop.
        return await anyio.to_thread.run_sync(self._extract_document, content)

    def _extract_document(self, content: bytes) -> ExtractedOcrText:
        document = pymupdf.open(stream=content, filetype="pdf")
        with document:
            if document.is_encrypted:
                raise OcrExtractionFailed("encrypted PDFs are not supported")
            page_count = cast(int, document.page_count)  # pyright: ignore[reportUnknownMemberType]
            if not 1 <= page_count <= self._max_pages:
                raise OcrExtractionFailed("PDF page count is outside the supported limit")
            extracted_pages: list[str] = []
            character_count = 0
            for page in document:
                text = anyio.from_thread.run(self._extract_page, self._rasterize_page(page))
                character_count += len(text) + bool(extracted_pages)
                if character_count > self._max_characters:
                    raise OcrTextLimitExceeded(self._max_characters)
                extracted_pages.append(text)

            extracted = "\f".join(extracted_pages)
            return ExtractedOcrText(
                text=extracted,
                page_count=page_count,
                character_count=len(extracted),
                non_whitespace_character_count=sum(not char.isspace() for char in extracted),
            )

    def _rasterize_page(self, page: pymupdf.Page) -> bytes:
        scale = self._raster_dpi / 72
        bounds = (page.rect * pymupdf.Matrix(scale, scale)).irect
        if bounds.width <= 0 or bounds.height <= 0:
            raise OcrExtractionFailed("PDF page has invalid raster dimensions")
        if bounds.width * bounds.height > self._max_page_pixels:
            raise OcrExtractionFailed(
                f"PDF page exceeds the {self._max_page_pixels}-pixel OCR raster limit"
            )
        pixmap = page.get_pixmap(  # pyright: ignore[reportUnknownMemberType]
            dpi=self._raster_dpi,
            alpha=False,
        )
        return cast(bytes, pixmap.tobytes("png"))

    async def _extract_page(self, image: bytes) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                self._command,
                "stdin",
                "stdout",
                "--dpi",
                str(self._raster_dpi),
                "-l",
                self._language,
                "--psm",
                "6",
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE,
            )
        except FileNotFoundError as error:
            raise OcrEngineUnavailable("configured Tesseract executable is unavailable") from error

        try:
            stdout, _ = await asyncio.wait_for(
                process.communicate(image), timeout=self._page_timeout_seconds
            )
        except TimeoutError as error:
            process.kill()
            await process.wait()
            raise OcrExtractionFailed("Tesseract exceeded the page timeout") from error
        if process.returncode != 0:
            raise OcrExtractionFailed("Tesseract could not process the page")
        try:
            return stdout.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise OcrExtractionFailed("Tesseract returned invalid UTF-8") from error
