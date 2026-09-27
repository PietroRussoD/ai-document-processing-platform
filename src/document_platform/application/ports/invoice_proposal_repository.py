"""Persistence contract for immutable AI-proposed invoice fields."""

from typing import Protocol
from uuid import UUID

from document_platform.domain.processing import AiInvoiceExtractionProposal


class InvoiceProposalAlreadyExists(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"AI invoice proposal already exists: {processing_run_id}")


class InvoiceProposalRepository(Protocol):
    async def add(self, proposal: AiInvoiceExtractionProposal) -> None: ...

    async def get(self, processing_run_id: UUID) -> AiInvoiceExtractionProposal | None: ...
