"""Tesseract PDF OCR adapter tests without a local Tesseract installation."""

from collections.abc import Sequence
from shutil import which

import pymupdf
import pytest

from document_platform.adapters.outbound.ocr import TesseractPdfOcrExtractor
from document_platform.adapters.outbound.ocr import tesseract_pdf_ocr_extractor as module
from document_platform.application.ports import (
    OcrEngineUnavailable,
    OcrTextLimitExceeded,
)


class FakeProcess:
    def __init__(self, *, stdout: bytes, returncode: int = 0) -> None:
        self._stdout = stdout
        self.returncode = returncode

    async def communicate(self, input: bytes) -> tuple[bytes, bytes]:
        assert input.startswith(b"\x89PNG")
        return self._stdout, b""

    def kill(self) -> None:
        return None

    async def wait(self) -> None:
        return None


def pdf_with_text(text: str) -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)  # pyright: ignore[reportUnknownMemberType]
    content = document.tobytes()  # pyright: ignore[reportUnknownMemberType]
    document.close()
    return content


def high_contrast_pdf() -> bytes:
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 120), "INVOICE 42", fontsize=36)  # pyright: ignore[reportUnknownMemberType]
    content = document.tobytes()  # pyright: ignore[reportUnknownMemberType]
    document.close()
    return content


def extractor(*, max_characters: int = 100) -> TesseractPdfOcrExtractor:
    return TesseractPdfOcrExtractor(
        command="tesseract",
        language="eng",
        max_pages=2,
        max_characters=max_characters,
        raster_dpi=200,
        page_timeout_seconds=1,
    )


@pytest.mark.anyio
async def test_rasterizes_pages_and_normalizes_tesseract_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[Sequence[str]] = []

    async def create_process(command: str, *args: str, **kwargs: object) -> FakeProcess:
        assert kwargs["stdin"] is not None
        commands.append((command, *args))
        return FakeProcess(stdout=b"Invoice 42\n")

    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", create_process)

    result = await extractor().extract(pdf_with_text("synthetic input"))

    assert result.text == "Invoice 42\n"
    assert result.page_count == 1
    assert result.character_count == 11
    assert result.non_whitespace_character_count == 9
    assert commands == [("tesseract", "stdin", "stdout", "--dpi", "200", "-l", "eng", "--psm", "6")]


@pytest.mark.anyio
async def test_reports_an_unavailable_tesseract_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def create_process(*args: object, **kwargs: object) -> FakeProcess:
        raise FileNotFoundError

    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", create_process)

    with pytest.raises(OcrEngineUnavailable, match="unavailable"):
        await extractor().extract(pdf_with_text("synthetic input"))


@pytest.mark.anyio
async def test_enforces_the_ocr_text_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    async def create_process(*args: object, **kwargs: object) -> FakeProcess:
        return FakeProcess(stdout=b"too long")

    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", create_process)

    with pytest.raises(OcrTextLimitExceeded, match="5-character"):
        await extractor(max_characters=5).extract(pdf_with_text("synthetic input"))


@pytest.mark.skipif(which("tesseract") is None, reason="Tesseract is not installed")
@pytest.mark.anyio
async def test_runs_tesseract_against_a_synthetic_pdf() -> None:
    result = await extractor().extract(high_contrast_pdf())

    assert "INVOICE" in result.text.upper()
    assert result.page_count == 1
