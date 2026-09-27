"""Persistence contract for terminal AI proposal provider failures."""

from typing import Protocol
from uuid import UUID

from document_platform.domain.processing import AiInvoiceProposalFailure


class InvoiceProposalFailureAlreadyExists(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"AI invoice proposal failure already exists: {processing_run_id}")


class InvoiceProposalOutcomeConflict(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"AI invoice proposal outcome already exists: {processing_run_id}")


class InvoiceProposalFailureRepository(Protocol):
    async def add(self, failure: AiInvoiceProposalFailure) -> None: ...

    async def get(self, processing_run_id: UUID) -> AiInvoiceProposalFailure | None: ...
