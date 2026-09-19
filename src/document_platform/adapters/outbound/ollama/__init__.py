"""Local Ollama adapters used by evaluation tooling."""

from document_platform.adapters.outbound.ollama.invoice_extraction_client import (
    OllamaInvoiceExtractionClient,
    OllamaInvoiceExtractionError,
    OllamaInvoiceExtractionSettings,
)

__all__ = [
    "OllamaInvoiceExtractionClient",
    "OllamaInvoiceExtractionError",
    "OllamaInvoiceExtractionSettings",
]
