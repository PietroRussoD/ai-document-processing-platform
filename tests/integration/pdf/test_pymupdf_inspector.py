"""PyMuPDF structural inspection integration tests."""

from pathlib import Path
from typing import cast

import pymupdf
import pytest

from document_platform.adapters.outbound.pdf import PyMuPdfInspector
from document_platform.application.ports import EncryptedPdf, InvalidPdf, PdfPageLimitExceeded


def _write_pdf(path: Path, *, pages: int, password: str | None = None) -> None:
    document = pymupdf.open()
    for _ in range(pages):
        document.new_page()

    if password is None:
        document.save(path)  # pyright: ignore[reportUnknownMemberType]
    else:
        encryption = cast(
            int,
            pymupdf.PDF_ENCRYPT_AES_256,  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
        )
        document.save(  # pyright: ignore[reportUnknownMemberType]
            path,
            encryption=encryption,
            owner_pw="owner-secret",
            user_pw=password,
        )
    document.close()


@pytest.mark.anyio
async def test_reports_the_page_count_of_a_valid_pdf(tmp_path: Path) -> None:
    path = tmp_path / "invoice.pdf"
    _write_pdf(path, pages=2)

    inspection = await PyMuPdfInspector(max_pages=10).inspect(path)

    assert inspection.page_count == 2


@pytest.mark.anyio
async def test_rejects_content_without_a_pdf_signature(tmp_path: Path) -> None:
    path = tmp_path / "invoice.pdf"
    path.write_bytes(b"not a PDF")

    with pytest.raises(InvalidPdf, match="signature"):
        await PyMuPdfInspector(max_pages=10).inspect(path)


@pytest.mark.anyio
async def test_rejects_a_corrupt_pdf(tmp_path: Path) -> None:
    path = tmp_path / "invoice.pdf"
    path.write_bytes(b"%PDF-1.7\ninvalid body")

    with pytest.raises(InvalidPdf, match="structurally valid"):
        await PyMuPdfInspector(max_pages=10).inspect(path)


@pytest.mark.anyio
async def test_rejects_an_encrypted_pdf(tmp_path: Path) -> None:
    path = tmp_path / "invoice.pdf"
    _write_pdf(path, pages=1, password="user-secret")

    with pytest.raises(EncryptedPdf):
        await PyMuPdfInspector(max_pages=10).inspect(path)


@pytest.mark.anyio
async def test_rejects_a_pdf_over_the_page_limit(tmp_path: Path) -> None:
    path = tmp_path / "invoice.pdf"
    _write_pdf(path, pages=2)

    with pytest.raises(PdfPageLimitExceeded, match="1-page limit"):
        await PyMuPdfInspector(max_pages=1).inspect(path)


def test_rejects_a_non_positive_page_limit() -> None:
    with pytest.raises(ValueError, match="max_pages must be positive"):
        PyMuPdfInspector(max_pages=0)
