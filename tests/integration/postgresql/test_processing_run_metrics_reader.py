"""PostgreSQL processing-run metrics read-model tests."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.adapters.outbound.postgresql.queries import (
    SqlAlchemyProcessingRunMetricsReader,
)
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyProcessingRunRepository,
)
from document_platform.domain.documents import Document
from document_platform.domain.processing import (
    ProcessingFailure,
    ProcessingFailureCode,
    ProcessingRun,
    ProcessingRunStatus,
    ProcessingStage,
)
from document_platform.settings import Settings

QUEUED_AT = datetime(2000, 1, 1, tzinfo=UTC)


@pytest.mark.anyio
async def test_reads_status_counts_and_oldest_queued_run(migrated_postgres_url: str) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    reader = SqlAlchemyProcessingRunMetricsReader(database.sessions)
    before = await reader.read()
    runs = _runs_for_every_status()

    try:
        async with database.sessions.begin() as session:
            documents = SqlAlchemyDocumentRepository(session)
            processing_runs = SqlAlchemyProcessingRunRepository(session)
            for run in runs:
                await documents.add(_document(run.document_id))
                await processing_runs.add(run)

        result = await reader.read()
    finally:
        await database.dispose()

    assert result.oldest_queued_at == QUEUED_AT
    for status in ProcessingRunStatus:
        assert result.counts_by_status.get(status, 0) == before.counts_by_status.get(status, 0) + 1
    failure_category = (
        ProcessingStage.EMBEDDED_TEXT_EXTRACTION,
        ProcessingFailureCode.ACTIVITY_RETRY_EXHAUSTED,
    )
    assert result.failure_counts_by_category.get(failure_category, 0) == (
        before.failure_counts_by_category.get(failure_category, 0) + 1
    )


def _runs_for_every_status() -> tuple[ProcessingRun, ...]:
    queued = _queued_run()
    running = _queued_run().start(at=QUEUED_AT + timedelta(seconds=1))
    waiting_retry = (
        _queued_run()
        .start(at=QUEUED_AT + timedelta(seconds=1))
        .wait_for_retry(at=QUEUED_AT + timedelta(seconds=2))
    )
    review_required = (
        _queued_run()
        .start(at=QUEUED_AT + timedelta(seconds=1))
        .require_review(at=QUEUED_AT + timedelta(seconds=2))
    )
    completed = (
        _queued_run()
        .start(at=QUEUED_AT + timedelta(seconds=1))
        .complete(at=QUEUED_AT + timedelta(seconds=2))
    )
    failed = (
        _queued_run()
        .start(at=QUEUED_AT + timedelta(seconds=1))
        .fail(
            at=QUEUED_AT + timedelta(seconds=2),
            failure=ProcessingFailure(
                stage=ProcessingStage.EMBEDDED_TEXT_EXTRACTION,
                code=ProcessingFailureCode.ACTIVITY_RETRY_EXHAUSTED,
            ),
        )
    )
    cancelled = _queued_run().cancel(at=QUEUED_AT + timedelta(seconds=1))
    return (queued, running, waiting_retry, review_required, completed, failed, cancelled)


def _queued_run() -> ProcessingRun:
    return ProcessingRun.queue(run_id=uuid4(), document_id=uuid4(), queued_at=QUEUED_AT)


def _document(document_id: UUID) -> Document:
    return Document.accept_pdf(
        document_id=document_id,
        original_filename="metrics-invoice.pdf",
        size_bytes=42_000,
        page_count=1,
        content_sha256=uuid4().hex * 2,
        storage_key=f"blobs/sha256/metrics/{uuid4().hex}",
        accepted_at=QUEUED_AT,
    )
