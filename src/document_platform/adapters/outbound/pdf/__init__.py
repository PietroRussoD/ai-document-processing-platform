"""PDF processing outbound adapters."""

from document_platform.adapters.outbound.pdf.pymupdf_inspector import PyMuPdfInspector
from document_platform.adapters.outbound.pdf.pymupdf_text_extractor import PyMuPdfTextExtractor

__all__ = ["PyMuPdfInspector", "PyMuPdfTextExtractor"]
