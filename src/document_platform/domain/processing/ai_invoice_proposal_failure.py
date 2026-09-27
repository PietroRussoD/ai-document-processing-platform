"""Terminal provider failure separate from document processing state."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from document_platform.domain.processing.ai_invoice_extraction_proposal import InvoiceModelProvider


class InvoiceProposalGenerationFailureCode(StrEnum):
    TIMEOUT = "TIMEOUT"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID_RESPONSE = "INVALID_RESPONSE"


class InvalidAiInvoiceProposalFailure(ValueError):
    """Raised when a terminal provider failure lacks safe provenance."""


@dataclass(frozen=True, slots=True)
class AiInvoiceProposalFailure:
    processing_run_id: UUID
    provider: InvoiceModelProvider
    model_reference: str
    code: InvoiceProposalGenerationFailureCode
    failed_at: datetime

    def __post_init__(self) -> None:
        if self.processing_run_id.int == 0:
            raise InvalidAiInvoiceProposalFailure("processing_run_id must not be the nil UUID")
        if type(self.provider) is not InvoiceModelProvider:
            raise InvalidAiInvoiceProposalFailure("provider must be a known model provider")
        if not self.model_reference.strip() or len(self.model_reference) > 200:
            raise InvalidAiInvoiceProposalFailure(
                "model_reference must contain 1 to 200 characters"
            )
        if type(self.code) is not InvoiceProposalGenerationFailureCode:
            raise InvalidAiInvoiceProposalFailure("code must be a known failure code")
        if self.failed_at.tzinfo is None or self.failed_at.utcoffset() is None:
            raise InvalidAiInvoiceProposalFailure("failed_at must be timezone-aware")
