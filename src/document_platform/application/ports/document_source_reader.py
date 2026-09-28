"""Resolve an accepted document identifier to its internal blob key."""

from typing import Protocol
from uuid import UUID


class DocumentSourceReader(Protocol):
    async def get_storage_key(self, document_id: UUID) -> str | None: ...
