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
