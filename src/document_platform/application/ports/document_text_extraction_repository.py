"""Persistence contract for immutable document text extractions."""

from typing import Protocol
from uuid import UUID

from document_platform.domain.processing import DocumentTextExtraction


class DocumentTextExtractionAlreadyExists(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"document text extraction already exists: {processing_run_id}")


class DocumentTextExtractionRepository(Protocol):
    async def add(self, extraction: DocumentTextExtraction) -> None: ...

    async def get(self, processing_run_id: UUID) -> DocumentTextExtraction | None: ...
