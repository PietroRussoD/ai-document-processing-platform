"""PyMuPDF embedded-text extraction integration tests."""

import pymupdf
import pytest

from document_platform.adapters.outbound.pdf import PyMuPdfTextExtractor
from document_platform.application.ports import PdfTextLimitExceeded


def pdf_with_text(*pages: str) -> bytes:
    document = pymupdf.open()
    for text in pages:
        page = document.new_page()
        page.insert_text((72, 72), text)  # pyright: ignore[reportUnknownMemberType]
    content = document.tobytes()  # pyright: ignore[reportUnknownMemberType]
    document.close()
    return content


@pytest.mark.anyio
async def test_extracts_text_and_quality_signals_from_each_page() -> None:
    extraction = await PyMuPdfTextExtractor(max_pages=2, max_characters=100).extract(
        pdf_with_text("Invoice 42", "Total 19.99")
    )

    assert extraction.page_count == 2
    assert extraction.text == "Invoice 42\n\fTotal 19.99\n"
    assert extraction.character_count == len(extraction.text)
    assert extraction.non_whitespace_character_count == 19


@pytest.mark.anyio
async def test_rejects_text_over_the_configured_limit() -> None:
    extractor = PyMuPdfTextExtractor(max_pages=1, max_characters=5)

    with pytest.raises(PdfTextLimitExceeded, match="5-character"):
        await extractor.extract(pdf_with_text("too long"))


@pytest.mark.parametrize(
    ("pages", "limit", "expected_text"),
    [(("A", "B"), 5, "A\n\fB\n"), (("", "", ""), 2, "\f\f")],
)
@pytest.mark.anyio
async def test_accepts_text_at_the_limit_including_page_separators(
    pages: tuple[str, ...], limit: int, expected_text: str
) -> None:
    extraction = await PyMuPdfTextExtractor(max_pages=len(pages), max_characters=limit).extract(
        pdf_with_text(*pages)
    )

    assert extraction.text == expected_text
    assert extraction.character_count == limit


@pytest.mark.parametrize(("pages", "limit"), [(("A", "B"), 4), (("", "", ""), 1)])
@pytest.mark.anyio
async def test_rejects_text_when_page_separators_exceed_the_limit(
    pages: tuple[str, ...], limit: int
) -> None:
    extractor = PyMuPdfTextExtractor(max_pages=len(pages), max_characters=limit)

    with pytest.raises(PdfTextLimitExceeded, match=f"{limit}-character"):
        await extractor.extract(pdf_with_text(*pages))
