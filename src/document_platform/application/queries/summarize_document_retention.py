"""Build a dry-run summary for documents past their retention period."""

from document_platform.application.ports import DocumentRetentionReader
from document_platform.application.ports.runtime import Clock
from document_platform.application.retention import (
    DocumentRetentionReport,
    calculate_retention_cutoff,
)


class SummarizeDocumentRetentionHandler:
    def __init__(self, reader: DocumentRetentionReader, clock: Clock) -> None:
        self._reader = reader
        self._clock = clock

    async def __call__(self, *, retention_days: int) -> DocumentRetentionReport:
        cutoff = calculate_retention_cutoff(retention_days=retention_days, now=self._clock())
        snapshot = await self._reader.summarize_candidates(cutoff=cutoff)
        return DocumentRetentionReport(
            retention_days=retention_days,
            cutoff=cutoff,
            snapshot=snapshot,
        )
