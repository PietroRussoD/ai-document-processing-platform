"""PostgreSQL document-retention candidate summary tests."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import PostgresDsn
from sqlalchemy import select

from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.adapters.outbound.postgresql.models import DocumentRecord
from document_platform.adapters.outbound.postgresql.queries import (
    SqlAlchemyDocumentRetentionDeleter,
    SqlAlchemyDocumentRetentionReader,
)
from document_platform.adapters.outbound.postgresql.repositories import SqlAlchemyDocumentRepository
from document_platform.domain.documents import Document, DocumentStatus
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
