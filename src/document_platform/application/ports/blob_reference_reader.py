"""Read whether a stored blob still belongs to any document."""

from collections.abc import Collection
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class BlobIdentity:
    key: str
    content_sha256: str


class BlobReferenceReader(Protocol):
    async def is_referenced(self, *, key: str, content_sha256: str) -> bool: ...

    async def find_referenced(self, blobs: Collection[BlobIdentity]) -> frozenset[BlobIdentity]: ...
