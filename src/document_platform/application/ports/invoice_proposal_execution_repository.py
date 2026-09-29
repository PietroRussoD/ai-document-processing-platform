"""Persistence contract for the separate advisory execution lifecycle."""

from typing import Protocol
from uuid import UUID

from document_platform.domain.processing import AiInvoiceProposalExecution


class AiInvoiceProposalExecutionAlreadyExists(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"AI proposal execution already exists: {processing_run_id}")


class ConcurrentAiInvoiceProposalExecutionUpdate(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"AI proposal execution changed or is missing: {processing_run_id}")


class InvoiceProposalExecutionRepository(Protocol):
    async def add(self, execution: AiInvoiceProposalExecution) -> None: ...

    async def get(self, processing_run_id: UUID) -> AiInvoiceProposalExecution | None: ...

    async def finish(self, execution: AiInvoiceProposalExecution) -> None: ...
