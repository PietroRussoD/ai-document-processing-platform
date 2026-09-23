"""Read-only summary of documents eligible for retention."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from document_platform.domain.documents import DocumentStatus


@dataclass(frozen=True, slots=True)
class DocumentRetentionSnapshot:
    counts_by_status: dict[DocumentStatus, int]
    total_size_bytes: int

    @property
    def document_count(self) -> int:
        return sum(self.counts_by_status.values())


class DocumentRetentionReader(Protocol):
    async def summarize_candidates(self, *, cutoff: datetime) -> DocumentRetentionSnapshot: ...
