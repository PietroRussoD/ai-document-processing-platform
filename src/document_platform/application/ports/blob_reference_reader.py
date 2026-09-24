"""Read whether a stored blob still belongs to any document."""

from typing import Protocol


class BlobReferenceReader(Protocol):
    async def is_referenced(self, *, key: str, content_sha256: str) -> bool: ...
