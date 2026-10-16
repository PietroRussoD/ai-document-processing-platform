"""Tesseract PDF OCR adapter tests without a local Tesseract installation."""

from collections.abc import Callable, Sequence
from shutil import which
from typing import cast

import pymupdf
import pytest

from document_platform.adapters.outbound.ocr import TesseractPdfOcrExtractor
from document_platform.adapters.outbound.ocr import tesseract_pdf_ocr_extractor as module
from document_platform.application.ports import (
    OcrEngineUnavailable,
    OcrExtractionFailed,
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


def pdf_with_page_sizes(sizes: Sequence[tuple[float, float]], *, rotation: int = 0) -> bytes:
    with pymupdf.open() as document:
        for width, height in sizes:
            page = document.new_page(width=width, height=height)
            page.set_rotation(rotation)  # pyright: ignore[reportUnknownMemberType]
        return document.tobytes()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]


def extractor(
    *, max_characters: int = 100, max_page_pixels: int = 20_000_000, raster_dpi: int = 200
) -> TesseractPdfOcrExtractor:
    return TesseractPdfOcrExtractor(
        command="tesseract",
        language="eng",
        max_pages=2,
        max_characters=max_characters,
        raster_dpi=raster_dpi,
        max_page_pixels=max_page_pixels,
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


@pytest.mark.parametrize(
    ("width", "height", "dpi", "limit"),
    [(100, 100, 72, 9_999), (10_000, 10_000, 200, 20_000_000), (72, 72, 144, 20_735)],
)
@pytest.mark.anyio
async def test_rejects_oversized_pages_before_pixmap_allocation_or_ocr(
    monkeypatch: pytest.MonkeyPatch, width: int, height: int, dpi: int, limit: int
) -> None:
    def forbidden_pixmap(*args: object, **kwargs: object) -> None:
        pytest.fail("oversized pages must not allocate a pixmap")

    async def forbidden_process(*args: object, **kwargs: object) -> FakeProcess:
        pytest.fail("oversized pages must not start Tesseract")

    monkeypatch.setattr(pymupdf.Page, "get_pixmap", forbidden_pixmap)
    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", forbidden_process)

    with pytest.raises(OcrExtractionFailed, match=f"{limit}-pixel OCR raster limit"):
        await extractor(max_page_pixels=limit, raster_dpi=dpi).extract(
            pdf_with_page_sizes([(width, height)])
        )


@pytest.mark.parametrize("rotation", [0, 90])
@pytest.mark.anyio
async def test_accepts_the_exact_pixel_limit_with_rotated_and_fractional_pages(
    monkeypatch: pytest.MonkeyPatch, rotation: int
) -> None:
    async def create_process(*args: object, **kwargs: object) -> FakeProcess:
        return FakeProcess(stdout=b"OK")

    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", create_process)

    # Fractional dimensions round outward at the chosen DPI: 101 by 51 pixels.
    result = await extractor(max_page_pixels=101 * 51, raster_dpi=144).extract(
        pdf_with_page_sizes([(50.25, 25.25)], rotation=rotation)
    )

    assert result.text == "OK"
    assert result.page_count == 1


@pytest.mark.anyio
async def test_finishes_each_page_ocr_before_rasterizing_the_next_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    original_get_pixmap = cast(
        Callable[..., pymupdf.Pixmap],
        pymupdf.Page.get_pixmap,  # pyright: ignore[reportUnknownMemberType]
    )

    def rasterize(page: pymupdf.Page, **kwargs: object) -> pymupdf.Pixmap:
        number = cast(int, page.number)  # pyright: ignore[reportUnknownMemberType]
        events.append(f"raster-{number}")
        return original_get_pixmap(page, **kwargs)

    class PageProcess(FakeProcess):
        async def communicate(self, input: bytes) -> tuple[bytes, bytes]:
            output = await super().communicate(input)
            events.append("ocr-finished")
            return output

    async def create_process(*args: object, **kwargs: object) -> FakeProcess:
        events.append("ocr")
        return PageProcess(stdout=b"page")

    monkeypatch.setattr(pymupdf.Page, "get_pixmap", rasterize)
    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", create_process)

    result = await extractor().extract(pdf_with_page_sizes([(100, 100), (100, 100)]))

    assert events == ["raster-0", "ocr", "ocr-finished", "raster-1", "ocr", "ocr-finished"]
    assert result.text == "page\fpage"
    assert result.page_count == 2
    assert result.character_count == 9
    assert result.non_whitespace_character_count == 8


@pytest.mark.anyio
async def test_counts_page_separators_against_the_total_text_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def create_process(*args: object, **kwargs: object) -> FakeProcess:
        return FakeProcess(stdout=b"OK")

    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", create_process)

    with pytest.raises(OcrTextLimitExceeded, match="4-character"):
        await extractor(max_characters=4).extract(pdf_with_page_sizes([(100, 100), (100, 100)]))


@pytest.mark.parametrize(
    ("stdout", "returncode", "message"),
    [(b"", 1, "could not process"), (b"\xff", 0, "invalid UTF-8")],
)
@pytest.mark.anyio
async def test_closes_the_document_and_stops_after_an_ocr_failure(
    monkeypatch: pytest.MonkeyPatch, stdout: bytes, returncode: int, message: str
) -> None:
    content = pdf_with_page_sizes([(100, 100), (100, 100)])
    original_open = pymupdf.open
    documents: list[pymupdf.Document] = []
    calls = 0

    def open_document(*, stream: bytes, filetype: str) -> pymupdf.Document:
        document = original_open(stream=stream, filetype=filetype)
        documents.append(document)
        return document

    async def create_process(*args: object, **kwargs: object) -> FakeProcess:
        nonlocal calls
        calls += 1
        return FakeProcess(stdout=stdout, returncode=returncode)

    monkeypatch.setattr(module.pymupdf, "open", open_document)
    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", create_process)

    with pytest.raises(OcrExtractionFailed, match=message):
        await extractor().extract(content)

    assert calls == 1
    assert len(documents) == 1
    assert documents[0].is_closed
