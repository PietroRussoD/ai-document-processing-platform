"""PostgreSQL document-retention candidate summary tests."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import PostgresDsn
from sqlalchemy import select

from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.adapters.outbound.postgresql.models import (
    DocumentRecord,
    ProcessingRunRecord,
    ReprocessingOperationRecord,
    UploadIdempotencyRecordRow,
)
from document_platform.adapters.outbound.postgresql.queries import (
    SqlAlchemyDocumentRetentionDeleter,
    SqlAlchemyDocumentRetentionReader,
)
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyProcessingRunRepository,
    SqlAlchemyReprocessingOperationRepository,
    SqlAlchemyUploadIdempotencyRepository,
)
from document_platform.application.upload_idempotency import (
    IdempotencyKey,
    UploadIdempotencyRecord,
    UploadRequestFingerprint,
)
from document_platform.domain.documents import Document, DocumentStatus
from document_platform.domain.processing import ProcessingRun, ReprocessingOperation
from document_platform.settings import Settings

CUTOFF = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
OLD_ACCEPTED_AT = CUTOFF - timedelta(days=90)


@pytest.mark.anyio
async def test_summarizes_only_old_terminal_documents(migrated_postgres_url: str) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    documents = (
        _terminal_document(DocumentStatus.APPROVED, 100, CUTOFF - timedelta(seconds=1)),
        _terminal_document(DocumentStatus.REJECTED, 200, CUTOFF - timedelta(days=1)),
        _terminal_document(DocumentStatus.FAILED, 300, CUTOFF - timedelta(days=2)),
        _terminal_document(DocumentStatus.REVIEW_REQUIRED, 400, CUTOFF - timedelta(days=3)),
        _terminal_document(DocumentStatus.PROCESSING, 500, CUTOFF - timedelta(days=4)),
        _terminal_document(DocumentStatus.APPROVED, 600, CUTOFF + timedelta(seconds=1)),
        _terminal_document(DocumentStatus.APPROVED, 700, CUTOFF),
    )
    try:
        async with database.sessions.begin() as session:
            repository = SqlAlchemyDocumentRepository(session)
            for document in documents:
                await repository.add(document)

        snapshot = await SqlAlchemyDocumentRetentionReader(database.sessions).summarize_candidates(
            cutoff=CUTOFF
        )
    finally:
        await database.dispose()

    assert snapshot.document_count == 3
    assert snapshot.total_size_bytes == 600
    assert snapshot.counts_by_status == {
        DocumentStatus.APPROVED: 1,
        DocumentStatus.REJECTED: 1,
        DocumentStatus.FAILED: 1,
    }


@pytest.mark.anyio
async def test_deletes_only_old_terminal_documents_and_reports_aggregate(
    migrated_postgres_url: str,
) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    cutoff = CUTOFF - timedelta(days=31)
    documents = (
        _terminal_document(DocumentStatus.APPROVED, 100, cutoff - timedelta(seconds=1)),
        _terminal_document(DocumentStatus.REJECTED, 200, cutoff - timedelta(days=1)),
        _terminal_document(DocumentStatus.FAILED, 300, cutoff - timedelta(days=2)),
        _terminal_document(DocumentStatus.REVIEW_REQUIRED, 400, cutoff - timedelta(days=3)),
        _terminal_document(DocumentStatus.PROCESSING, 500, cutoff - timedelta(days=4)),
        _terminal_document(DocumentStatus.APPROVED, 600, cutoff + timedelta(seconds=1)),
        _terminal_document(DocumentStatus.APPROVED, 700, cutoff),
    )
    try:
        async with database.sessions.begin() as session:
            repository = SqlAlchemyDocumentRepository(session)
            for document in documents:
                await repository.add(document)

        snapshot = await SqlAlchemyDocumentRetentionDeleter(database.sessions).delete_candidates(
            cutoff=cutoff
        )
        async with database.sessions() as session:
            remaining = set(
                await session.scalars(
                    select(DocumentRecord.id).where(
                        DocumentRecord.id.in_([document.id for document in documents])
                    )
                )
            )
    finally:
        await database.dispose()

    assert snapshot.document_count == 3
    assert snapshot.total_size_bytes == 600
    assert snapshot.counts_by_status == {
        DocumentStatus.APPROVED: 1,
        DocumentStatus.REJECTED: 1,
        DocumentStatus.FAILED: 1,
    }
    assert remaining == {document.id for document in documents[3:]}


@pytest.mark.anyio
async def test_deletes_document_with_processing_and_reprocessing_evidence(
    migrated_postgres_url: str,
) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    cutoff = datetime(2024, 1, 1, tzinfo=UTC)
    accepted_at = cutoff - timedelta(days=10)
    source_started_at = accepted_at + timedelta(hours=1)
    source_completed_at = accepted_at + timedelta(hours=2)
    reprocessed_at = accepted_at + timedelta(days=1)
    replacement_started_at = reprocessed_at + timedelta(hours=1)
    replacement_completed_at = reprocessed_at + timedelta(hours=2)
    document_id = uuid4()
    source_run_id = uuid4()
    replacement_run_id = uuid4()
    operation_id = uuid4()
    idempotency_key = f"retention-{uuid4().hex}"

    document = (
        Document.accept_pdf(
            document_id=document_id,
            original_filename="retention-lineage.pdf",
            size_bytes=321,
            page_count=1,
            content_sha256=document_id.hex * 2,
            storage_key=f"blobs/{document_id}",
            accepted_at=accepted_at,
        )
        .start_processing(at=source_started_at)
        .approve(at=source_completed_at)
        .reopen_for_reprocessing(at=reprocessed_at)
        .approve(at=replacement_completed_at)
    )
    source_run = (
        ProcessingRun.queue(
            run_id=source_run_id,
            document_id=document_id,
            queued_at=accepted_at,
        )
        .start(at=source_started_at)
        .complete(at=source_completed_at)
    )
    replacement_run = (
        ProcessingRun.queue(
            run_id=replacement_run_id,
            document_id=document_id,
            previous_run_id=source_run_id,
            queued_at=reprocessed_at,
        )
        .start(at=replacement_started_at)
        .complete(at=replacement_completed_at)
    )
    operation = ReprocessingOperation.request(
        operation_id=operation_id,
        document_id=document_id,
        source_run_id=source_run_id,
        replacement_run_id=replacement_run_id,
        requested_by="retention-test-operator",
        reason="Reprocess after a corrected configuration.",
        idempotency_key=f"reprocess-{uuid4().hex}",
        requested_at=reprocessed_at,
    )
    upload_record = UploadIdempotencyRecord(
        key=IdempotencyKey(idempotency_key),
        request_fingerprint=UploadRequestFingerprint.create(
            original_filename=document.original_filename,
            media_type=document.media_type,
            content_sha256=document.content_sha256,
        ),
        processing_run_id=source_run_id,
        recorded_at=accepted_at,
    )

    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            runs = SqlAlchemyProcessingRunRepository(session)
            await runs.add(source_run)
            await runs.add(replacement_run)
            await SqlAlchemyReprocessingOperationRepository(session).add(operation)
            await SqlAlchemyUploadIdempotencyRepository(session).add(upload_record)

        snapshot = await SqlAlchemyDocumentRetentionDeleter(database.sessions).delete_candidates(
            cutoff=cutoff
        )
        async with database.sessions() as session:
            remaining = (
                await session.get(DocumentRecord, document_id),
                await session.get(ProcessingRunRecord, source_run_id),
                await session.get(ProcessingRunRecord, replacement_run_id),
                await session.get(ReprocessingOperationRecord, operation_id),
                await session.get(UploadIdempotencyRecordRow, idempotency_key),
            )
    finally:
        await database.dispose()

    assert snapshot.document_count == 1
    assert snapshot.total_size_bytes == 321
    assert snapshot.counts_by_status == {DocumentStatus.APPROVED: 1}
    assert remaining == (None,) * 5


def _terminal_document(
    status: DocumentStatus,
    size_bytes: int,
    status_changed_at: datetime,
) -> Document:
    accepted_at = min(OLD_ACCEPTED_AT, status_changed_at)
    document = Document.accept_pdf(
        document_id=uuid4(),
        original_filename=f"synthetic-{uuid4()}.pdf",
        size_bytes=size_bytes,
        page_count=1,
        content_sha256=uuid4().hex * 2,
        storage_key=f"blobs/sha256/{uuid4().hex[:2]}/{uuid4().hex * 2}",
        accepted_at=accepted_at,
    )
    if status is DocumentStatus.UPLOADED:
        return document

    processing_at = accepted_at + timedelta(seconds=1)
    document = document.start_processing(at=processing_at)
    if status is DocumentStatus.PROCESSING:
        return document
    if status is DocumentStatus.REVIEW_REQUIRED:
        return document.require_review(at=status_changed_at)
    if status is DocumentStatus.APPROVED:
        return document.approve(at=status_changed_at)
    if status is DocumentStatus.REJECTED:
        return document.require_review(at=status_changed_at - timedelta(seconds=1)).reject(
            at=status_changed_at
        )
    return document.fail(at=status_changed_at)
