"""Binary object storage contract."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StoredBlob:
    key: str
    content_sha256: str
    size_bytes: int


class EmptyBlob(ValueError):
    def __init__(self) -> None:
        super().__init__("blob must not be empty")


class BlobTooLarge(ValueError):
    def __init__(self, max_bytes: int) -> None:
        super().__init__(f"blob exceeds the {max_bytes}-byte limit")


class BlobIntegrityConflict(RuntimeError):
    def __init__(self, key: str) -> None:
        super().__init__(f"stored blob does not match its content-derived key: {key}")


class BlobStore(Protocol):
    async def store(self, source: Path) -> StoredBlob: ...
