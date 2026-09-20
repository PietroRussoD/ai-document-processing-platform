"""Document persistence contract."""

from typing import Protocol
from uuid import UUID

from document_platform.domain.documents import Document


class DocumentAlreadyExists(RuntimeError):
    def __init__(self, document_id: UUID) -> None:
        super().__init__(f"document already exists: {document_id}")


class ConcurrentDocumentUpdate(RuntimeError):
    def __init__(self, document_id: UUID) -> None:
        super().__init__(f"document was concurrently updated: {document_id}")


class DocumentRepository(Protocol):
    async def add(self, document: Document) -> None: ...

    async def get(self, document_id: UUID) -> Document | None: ...

    async def get_for_update(self, document_id: UUID) -> Document | None: ...

    async def update(self, document: Document) -> None: ...
