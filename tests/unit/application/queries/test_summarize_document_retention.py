"""Document-retention dry-run query tests."""

from datetime import UTC, datetime, timedelta

import pytest

from document_platform.application.ports import DocumentRetentionSnapshot
from document_platform.application.queries import (
    InvalidRetentionPeriod,
    SummarizeDocumentRetentionHandler,
)
from document_platform.domain.documents import DocumentStatus

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


class StubDocumentRetentionReader:
    def __init__(self, snapshot: DocumentRetentionSnapshot) -> None:
        self.snapshot = snapshot
        self.cutoffs: list[datetime] = []

    async def summarize_candidates(self, *, cutoff: datetime) -> DocumentRetentionSnapshot:
        self.cutoffs.append(cutoff)
        return self.snapshot


@pytest.mark.anyio
async def test_summarizes_candidates_before_the_calculated_cutoff() -> None:
    snapshot = DocumentRetentionSnapshot(
        counts_by_status={DocumentStatus.APPROVED: 2, DocumentStatus.FAILED: 1},
        total_size_bytes=12_000,
    )
    reader = StubDocumentRetentionReader(snapshot)

    report = await SummarizeDocumentRetentionHandler(reader, clock=lambda: NOW)(retention_days=30)

    assert report.cutoff == NOW - timedelta(days=30)
    assert report.snapshot == snapshot
    assert report.snapshot.document_count == 3
    assert reader.cutoffs == [report.cutoff]


@pytest.mark.anyio
@pytest.mark.parametrize("retention_days", [0, -1])
async def test_rejects_non_positive_retention_period(retention_days: int) -> None:
    reader = StubDocumentRetentionReader(DocumentRetentionSnapshot({}, 0))
    handler = SummarizeDocumentRetentionHandler(reader, clock=lambda: NOW)

    with pytest.raises(InvalidRetentionPeriod, match="must be positive"):
        await handler(retention_days=retention_days)

    assert reader.cutoffs == []


@pytest.mark.anyio
async def test_rejects_a_naive_clock() -> None:
    reader = StubDocumentRetentionReader(DocumentRetentionSnapshot({}, 0))
    handler = SummarizeDocumentRetentionHandler(
        reader,
        clock=lambda: datetime(2026, 9, 23, 12, 0),
    )

    with pytest.raises(InvalidRetentionPeriod, match="timezone-aware"):
        await handler(retention_days=30)

    assert reader.cutoffs == []
