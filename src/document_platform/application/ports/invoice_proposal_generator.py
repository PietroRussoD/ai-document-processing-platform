"""Bounded input and generation contract for invoice-proposal providers."""

import hashlib
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from document_platform.domain.processing import AiInvoiceExtractionProposal

MAX_SELECTED_TEXT_CHARACTERS = 20_000


class InvalidInvoiceProposalRequest(ValueError):
    """Raised when selected text cannot be sent to an invoice model."""


class InvoiceProposalInputTooLarge(InvalidInvoiceProposalRequest):
    def __init__(self, max_characters: int) -> None:
        super().__init__(f"selected invoice text exceeds the {max_characters}-character limit")
        self.max_characters = max_characters


@dataclass(frozen=True, slots=True)
class InvoiceProposalRequest:
    processing_run_id: UUID
    selected_text: str

    def __post_init__(self) -> None:
        if self.processing_run_id.int == 0:
            raise InvalidInvoiceProposalRequest("processing_run_id must not be the nil UUID")
        if not self.selected_text.strip():
            raise InvalidInvoiceProposalRequest("selected_text must not be blank")
        if len(self.selected_text) > MAX_SELECTED_TEXT_CHARACTERS:
            raise InvoiceProposalInputTooLarge(MAX_SELECTED_TEXT_CHARACTERS)

    @property
    def selected_text_sha256(self) -> str:
        return hashlib.sha256(self.selected_text.encode("utf-8")).hexdigest()


class InvoiceProposalGenerator(Protocol):
    """Generate a structured proposal from bounded canonical document text."""

    async def generate(self, request: InvoiceProposalRequest) -> AiInvoiceExtractionProposal: ...
