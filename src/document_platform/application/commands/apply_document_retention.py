"""Apply database-only document retention after computing its cutoff."""

from document_platform.application.ports import DocumentRetentionDeleter
from document_platform.application.ports.runtime import Clock
from document_platform.application.retention import (
    DocumentRetentionReport,
    calculate_retention_cutoff,
)


class ApplyDocumentRetentionHandler:
    def __init__(self, deleter: DocumentRetentionDeleter, clock: Clock) -> None:
        self._deleter = deleter
        self._clock = clock

    async def __call__(self, *, retention_days: int) -> DocumentRetentionReport:
        cutoff = calculate_retention_cutoff(retention_days=retention_days, now=self._clock())
        snapshot = await self._deleter.delete_candidates(cutoff=cutoff)
        return DocumentRetentionReport(
            retention_days=retention_days,
            cutoff=cutoff,
            snapshot=snapshot,
        )
