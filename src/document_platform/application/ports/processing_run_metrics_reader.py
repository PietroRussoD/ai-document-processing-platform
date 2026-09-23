"""Read-only operational snapshot for durable processing-run metrics."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from document_platform.domain.processing import (
    ProcessingFailureCode,
    ProcessingRunStatus,
    ProcessingStage,
)


@dataclass(frozen=True, slots=True)
class ProcessingRunMetricsSnapshot:
    counts_by_status: dict[ProcessingRunStatus, int]
    oldest_queued_at: datetime | None
    failure_counts_by_category: dict[tuple[ProcessingStage, ProcessingFailureCode], int]


class ProcessingRunMetricsReader(Protocol):
    async def read(self) -> ProcessingRunMetricsSnapshot: ...
