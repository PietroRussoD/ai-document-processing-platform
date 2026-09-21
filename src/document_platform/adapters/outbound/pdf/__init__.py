"""PDF processing outbound adapters."""

from document_platform.adapters.outbound.pdf.local_fault_injecting_pdf_text_extractor import (
    LocalFaultInjectingPdfTextExtractor,
)
from document_platform.adapters.outbound.pdf.pymupdf_inspector import PyMuPdfInspector
from document_platform.adapters.outbound.pdf.pymupdf_text_extractor import PyMuPdfTextExtractor

__all__ = [
    "LocalFaultInjectingPdfTextExtractor",
    "PyMuPdfInspector",
    "PyMuPdfTextExtractor",
]
