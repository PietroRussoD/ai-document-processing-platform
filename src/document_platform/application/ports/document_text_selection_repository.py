"""Persistence contract for immutable canonical-text selections."""

from typing import Protocol
from uuid import UUID

from document_platform.domain.processing import DocumentTextSelection


class DocumentTextSelectionAlreadyExists(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"document text selection already exists: {processing_run_id}")


class DocumentTextSelectionRepository(Protocol):
    async def add(self, selection: DocumentTextSelection) -> None: ...

    async def get(self, processing_run_id: UUID) -> DocumentTextSelection | None: ...
