"""Persistence contract for immutable document classifications."""

from typing import Protocol
from uuid import UUID

from document_platform.domain.processing import DocumentClassification


class DocumentClassificationAlreadyExists(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"document classification already exists: {processing_run_id}")


class DocumentClassificationRepository(Protocol):
    async def add(self, classification: DocumentClassification) -> None: ...

    async def get(self, processing_run_id: UUID) -> DocumentClassification | None: ...
