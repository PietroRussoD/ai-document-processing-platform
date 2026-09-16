"""Persistence contract for immutable OCR results."""

from typing import Protocol
from uuid import UUID

from document_platform.domain.processing import DocumentOcrExtraction


class DocumentOcrExtractionAlreadyExists(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"document OCR extraction already exists: {processing_run_id}")


class DocumentOcrExtractionRepository(Protocol):
    async def add(self, extraction: DocumentOcrExtraction) -> None: ...

    async def get(self, processing_run_id: UUID) -> DocumentOcrExtraction | None: ...
