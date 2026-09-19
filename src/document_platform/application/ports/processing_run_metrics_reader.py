"""Read-only operational snapshot for durable processing-run metrics."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from document_platform.domain.processing import ProcessingRunStatus


@dataclass(frozen=True, slots=True)
class ProcessingRunMetricsSnapshot:
    counts_by_status: dict[ProcessingRunStatus, int]
    oldest_queued_at: datetime | None


class ProcessingRunMetricsReader(Protocol):
    async def read(self) -> ProcessingRunMetricsSnapshot: ...
