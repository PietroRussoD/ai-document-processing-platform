"""Build a dry-run summary for documents past their retention period."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from document_platform.application.ports import (
    DocumentRetentionReader,
    DocumentRetentionSnapshot,
)
from document_platform.application.ports.runtime import Clock


class InvalidRetentionPeriod(ValueError):
    """Raised when a retention period is missing or invalid."""


@dataclass(frozen=True, slots=True)
class DocumentRetentionReport:
    retention_days: int
    cutoff: datetime
    snapshot: DocumentRetentionSnapshot


class SummarizeDocumentRetentionHandler:
    def __init__(self, reader: DocumentRetentionReader, clock: Clock) -> None:
        self._reader = reader
        self._clock = clock

    async def __call__(self, *, retention_days: int) -> DocumentRetentionReport:
        if retention_days < 1:
            raise InvalidRetentionPeriod("retention_days must be positive")

        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise InvalidRetentionPeriod("clock must return a timezone-aware datetime")

        cutoff = now - timedelta(days=retention_days)
        snapshot = await self._reader.summarize_candidates(cutoff=cutoff)
        return DocumentRetentionReport(
            retention_days=retention_days,
            cutoff=cutoff,
            snapshot=snapshot,
        )
