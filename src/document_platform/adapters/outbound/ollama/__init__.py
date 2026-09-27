"""Local Ollama adapters used by evaluation tooling."""

from document_platform.adapters.outbound.ollama.invoice_extraction_client import (
    OllamaInvoiceExtractionClient,
    OllamaInvoiceExtractionError,
    OllamaInvoiceExtractionSettings,
)
from document_platform.adapters.outbound.ollama.invoice_proposal_adapter import (
    OllamaInvoiceProposalAdapter,
    OllamaInvoiceProposalError,
    OllamaInvoiceProposalSettings,
)

__all__ = [
    "OllamaInvoiceProposalAdapter",
    "OllamaInvoiceProposalError",
    "OllamaInvoiceProposalSettings",
    "OllamaInvoiceExtractionClient",
    "OllamaInvoiceExtractionError",
    "OllamaInvoiceExtractionSettings",
]
