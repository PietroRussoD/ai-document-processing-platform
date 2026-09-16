"""Get-document-status query tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from document_platform.application.ports import (
    DocumentStatusView,
    ProcessingRunStatusView,
)
from document_platform.application.queries import DocumentNotFound, GetDocumentStatusHandler
from document_platform.domain.documents import DocumentStatus
from document_platform.domain.processing import ProcessingRunStatus

DOCUMENT_ID = UUID("11111111-1111-4111-8111-111111111111")
RUN_ID = UUID("22222222-2222-4222-8222-222222222222")
ACCEPTED_AT = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)


class StubDocumentStatusReader:
    def __init__(self, result: DocumentStatusView | None) -> None:
        self.result = result
        self.requested_ids: list[UUID] = []

    async def get(self, document_id: UUID) -> DocumentStatusView | None:
        self.requested_ids.append(document_id)
        return self.result


def document_view() -> DocumentStatusView:
    return DocumentStatusView(
        id=DOCUMENT_ID,
        original_filename="supplier-invoice.pdf",
        media_type="application/pdf",
        size_bytes=42_000,
        page_count=2,
        content_sha256="a" * 64,
        status=DocumentStatus.UPLOADED,
        accepted_at=ACCEPTED_AT,
        status_changed_at=ACCEPTED_AT,
        current_run=ProcessingRunStatusView(
            id=RUN_ID,
            status=ProcessingRunStatus.QUEUED,
            queued_at=ACCEPTED_AT,
            started_at=None,
            status_changed_at=ACCEPTED_AT,
            finished_at=None,
            attempt_count=0,
            processing_output=None,
        ),
    )


@pytest.mark.anyio
async def test_returns_the_document_status_projection() -> None:
    expected = document_view()
    reader = StubDocumentStatusReader(expected)

    result = await GetDocumentStatusHandler(reader)(DOCUMENT_ID)

    assert result == expected
    assert reader.requested_ids == [DOCUMENT_ID]


@pytest.mark.anyio
async def test_rejects_an_unknown_document() -> None:
    reader = StubDocumentStatusReader(None)

    with pytest.raises(DocumentNotFound, match=str(DOCUMENT_ID)):
        await GetDocumentStatusHandler(reader)(DOCUMENT_ID)

    assert reader.requested_ids == [DOCUMENT_ID]
