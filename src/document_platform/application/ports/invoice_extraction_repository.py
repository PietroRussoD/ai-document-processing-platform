"""Persistence contract for immutable structured invoice extractions."""

from typing import Protocol
from uuid import UUID

from document_platform.domain.processing import InvoiceExtraction


class InvoiceExtractionAlreadyExists(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"invoice extraction already exists: {processing_run_id}")


class InvoiceExtractionRepository(Protocol):
    async def add(self, extraction: InvoiceExtraction) -> None: ...

    async def get(self, processing_run_id: UUID) -> InvoiceExtraction | None: ...
