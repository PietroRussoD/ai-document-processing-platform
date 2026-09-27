"""PostgreSQL operator work-queue read-model tests."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.adapters.outbound.postgresql.queries import SqlAlchemyDocumentStatusReader
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyProcessingRunRepository,
)
from document_platform.application.ports import DocumentWorkQueue
from document_platform.domain.documents import Document
from document_platform.domain.processing import (
    ProcessingFailure,
    ProcessingFailureCode,
    ProcessingRun,
    ProcessingStage,
)
from document_platform.settings import Settings

ACCEPTED_AT = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)


@pytest.mark.anyio
async def test_lists_current_active_review_and_failed_work(
    migrated_postgres_url: str,
) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    documents = [
        Document.accept_pdf(
            document_id=uuid4(),
            original_filename=filename,
            size_bytes=42_000,
            page_count=2,
            content_sha256=digest * 64,
            storage_key=f"blobs/sha256/{digest}/{digest * 64}",
            accepted_at=ACCEPTED_AT + timedelta(minutes=index),
        )
        for index, (filename, digest) in enumerate(
            (("active.pdf", "a"), ("review.pdf", "b"), ("failed.pdf", "c"))
        )
    ]
    active_document, review_document, failed_document = documents
    review_time = ACCEPTED_AT + timedelta(minutes=4)
    failure_time = ACCEPTED_AT + timedelta(minutes=5)
    review_document = review_document.start_processing(at=review_time - timedelta(seconds=1))
    review_document = review_document.require_review(at=review_time)
    failed_document = failed_document.start_processing(at=failure_time - timedelta(seconds=1))
    failed_document = failed_document.fail(at=failure_time)
    unsupported_document = (
        Document.accept_pdf(
            document_id=uuid4(),
            original_filename="unrelated.pdf",
            size_bytes=42_000,
            page_count=1,
            content_sha256="d" * 64,
            storage_key="blobs/sha256/dd/" + "d" * 64,
            accepted_at=failure_time + timedelta(minutes=1),
        )
        .start_processing(at=failure_time + timedelta(minutes=1, seconds=1))
        .mark_unsupported(at=failure_time + timedelta(minutes=1, seconds=2))
    )

    active_run = ProcessingRun.queue(
        run_id=uuid4(), document_id=active_document.id, queued_at=ACCEPTED_AT
    )
    review_run = (
        ProcessingRun.queue(run_id=uuid4(), document_id=review_document.id, queued_at=ACCEPTED_AT)
        .start(at=review_time - timedelta(seconds=1))
        .require_review(at=review_time)
    )
    failed_run = (
        ProcessingRun.queue(run_id=uuid4(), document_id=failed_document.id, queued_at=ACCEPTED_AT)
        .start(at=failure_time - timedelta(seconds=1))
        .fail(
            at=failure_time,
            failure=ProcessingFailure(
                stage=ProcessingStage.OCR_TEXT_EXTRACTION,
                code=ProcessingFailureCode.ACTIVITY_RETRY_EXHAUSTED,
            ),
        )
    )
    unsupported_run = (
        ProcessingRun.queue(
            run_id=uuid4(),
            document_id=unsupported_document.id,
            queued_at=unsupported_document.accepted_at,
        )
        .start(at=unsupported_document.accepted_at + timedelta(seconds=1))
        .complete(at=unsupported_document.status_changed_at)
    )

    try:
        async with database.sessions.begin() as session:
            document_repository = SqlAlchemyDocumentRepository(session)
            run_repository = SqlAlchemyProcessingRunRepository(session)
            for document in (
                active_document,
                review_document,
                failed_document,
                unsupported_document,
            ):
                await document_repository.add(document)
            for run in (active_run, review_run, failed_run, unsupported_run):
                await run_repository.add(run)

        reader = SqlAlchemyDocumentStatusReader(database.sessions)
        active_page = await reader.list_queue(DocumentWorkQueue.ACTIVE, limit=100, offset=0)
        review_page = await reader.list_queue(DocumentWorkQueue.REVIEW, limit=100, offset=0)
        failed_page = await reader.list_queue(DocumentWorkQueue.FAILED, limit=100, offset=0)
        unsupported_page = await reader.list_queue(
            DocumentWorkQueue.UNSUPPORTED, limit=100, offset=0
        )
    finally:
        await database.dispose()

    assert active_page.total >= 1
    assert active_page.limit == 100
    assert active_page.offset == 0
    assert active_document.id in {item.document_id for item in active_page.items}
    assert review_page.total >= 1
    review_item = next(item for item in review_page.items if item.document_id == review_document.id)
    assert review_item.status.value == "REVIEW_REQUIRED"
    assert failed_page.total >= 1
    failed_item = next(item for item in failed_page.items if item.document_id == failed_document.id)
    assert failed_item.failure is not None
    assert failed_item.failure.stage is ProcessingStage.OCR_TEXT_EXTRACTION
    unsupported_item = next(
        item for item in unsupported_page.items if item.document_id == unsupported_document.id
    )
    assert unsupported_item.status.value == "UNSUPPORTED"
