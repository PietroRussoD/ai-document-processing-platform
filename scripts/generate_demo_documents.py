"""Generate the versioned, synthetic PDFs used by the local demonstration."""

import hashlib
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "examples/documents"
METADATA = {
    "author": "AI Document Processing Platform",
    "creator": "generate_demo_documents.py",
    "creationDate": "D:20260927000000Z",
    "modDate": "D:20260927000000Z",
    "producer": "PyMuPDF",
}


def _set_stable_pdf_id(document: pymupdf.Document, path: Path) -> None:
    identifier = hashlib.sha256(path.name.encode("utf-8")).hexdigest()[:32].upper()
    document.xref_set_key(-1, "ID", f"[<{identifier}><{identifier}>]")


INVOICE_TEXT = (
    "INVOICE\n"
    "Invoice number: DEMO-INV-1001\n"
    "Invoice date: 2026-09-15\n"
    "Supplier: Northstar Office Supplies Ltd\n"
    "Customer: Example Research Group\n"
    "Total amount: EUR 1240.50\n"
    "Payment terms: 30 days from invoice date\n"
    "Synthetic sample. No real company or transaction is represented.\n"
)
SCANNED_INVOICE_TEXT = (
    "INVOICE\n"
    "Invoice number: DEMO-INV-1002\n"
    "Invoice date: 2026-09-18\n"
    "Supplier: Cedar Lane Technology Ltd\n"
    "Customer: Example Research Group\n"
    "Total amount: EUR 875.25\n"
    "Payment terms: 14 days from invoice date\n"
    "Synthetic sample. No real company or transaction is represented.\n"
)
REPORT_TEXT = (
    "EQUIPMENT INSPECTION REPORT\n"
    "Inspection reference: DEMO-REPORT-2001\n"
    "Inspection date: 2026-09-20\n"
    "Location: Example Research Group, Building A\n"
    "The ventilation system operated within its normal range during inspection.\n"
    "Filters were replaced and the control panel passed its operational check.\n"
    "This synthetic report contains no real company or personal information.\n"
)


def _save_text_pdf(path: Path, text: str, *, title: str) -> None:
    document = pymupdf.open()
    try:
        page = document.new_page(width=595, height=842)
        page.insert_textbox(
            pymupdf.Rect(60, 60, 535, 780),
            text,
            fontname="helv",
            fontsize=12,
            lineheight=1.6,
        )
        document.set_metadata({**METADATA, "title": title, "subject": "Synthetic demo fixture"})
        _set_stable_pdf_id(document, path)
        document.save(path, garbage=4, deflate=True, no_new_id=True)
    finally:
        document.close()


def _save_scanned_pdf(path: Path) -> None:
    rendered_document = pymupdf.open()
    try:
        page = rendered_document.new_page(width=595, height=842)
        page.insert_textbox(
            pymupdf.Rect(60, 70, 535, 780),
            SCANNED_INVOICE_TEXT,
            fontname="helv",
            fontsize=18,
            lineheight=1.8,
        )
        pixmap = page.get_pixmap(dpi=300, alpha=False)
        image = pixmap.tobytes("png")
    finally:
        rendered_document.close()

    document = pymupdf.open()
    try:
        page = document.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=image)
        document.set_metadata(
            {**METADATA, "title": "Synthetic scanned invoice", "subject": "Synthetic demo fixture"}
        )
        _set_stable_pdf_id(document, path)
        document.save(path, garbage=4, deflate=True, no_new_id=True)
    finally:
        document.close()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    _save_text_pdf(OUTPUT / "invoice-digital.pdf", INVOICE_TEXT, title="Synthetic digital invoice")
    _save_scanned_pdf(OUTPUT / "invoice-scanned.pdf")
    _save_text_pdf(
        OUTPUT / "equipment-report.pdf", REPORT_TEXT, title="Synthetic inspection report"
    )
    print(f"Generated three synthetic documents in {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
