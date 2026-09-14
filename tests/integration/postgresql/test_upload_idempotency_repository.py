"""SQLAlchemy upload idempotency repository integration tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import PostgresDsn
from sqlalchemy.exc import IntegrityError

from document_platform.adapters.outbound.postgresql.database import Database, create_database
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyProcessingRunRepository,
    SqlAlchemyUploadIdempotencyRepository,
)
from document_platform.application.ports import UploadIdempotencyRecordAlreadyExists
from document_platform.application.upload_idempotency import (
    IdempotencyKey,
    UploadIdempotencyRecord,
    UploadRequestFingerprint,
)
from document_platform.domain.documents import Document
from document_platform.domain.processing import ProcessingRun
from document_platform.settings import Settings

RECORDED_AT = datetime(2026, 9, 14, 14, 0, tzinfo=UTC)


def _database_for(postgres_url: str) -> Database:
    return create_database(Settings(environment="test", database_url=PostgresDsn(postgres_url)))


def _document(document_id: UUID) -> Document:
    return Document.accept_pdf(
        document_id=document_id,
        original_filename="idempotency-repository-test.pdf",
        size_bytes=1_000,
        page_count=1,
        content_sha256=document_id.hex * 2,
        storage_key=f"blobs/{document_id}",
        accepted_at=RECORDED_AT,
    )


def _run(run_id: UUID, document_id: UUID) -> ProcessingRun:
    return ProcessingRun.queue(run_id=run_id, document_id=document_id, queued_at=RECORDED_AT)


def _record(key: str, run_id: UUID) -> UploadIdempotencyRecord:
    return UploadIdempotencyRecord(
        key=IdempotencyKey(key),
        request_fingerprint=UploadRequestFingerprint("a" * 64),
        processing_run_id=run_id,
        recorded_at=RECORDED_AT,
    )


async def _add_document_and_run(
    database: Database,
    document: Document,
    run: ProcessingRun,
) -> None:
    async with database.sessions.begin() as session:
        await SqlAlchemyDocumentRepository(session).add(document)
        await SqlAlchemyProcessingRunRepository(session).add(run)


@pytest.mark.anyio
async def test_adds_and_loads_an_upload_idempotency_record(
    migrated_postgres_url: str,
) -> None:
    database = _database_for(migrated_postgres_url)
    document = _document(UUID("21212121-2121-4121-8121-212121212121"))
    run = _run(UUID("22222222-2222-4222-8222-222222222222"), document.id)
    record = _record("repository-test", run.id)

    try:
        await _add_document_and_run(database, document, run)
        async with database.sessions.begin() as session:
            await SqlAlchemyUploadIdempotencyRepository(session).add(record)

        async with database.sessions() as session:
            loaded = await SqlAlchemyUploadIdempotencyRepository(session).get(record.key)
    finally:
        await database.dispose()

    assert loaded == record


@pytest.mark.anyio
async def test_returns_none_for_an_unknown_idempotency_key(
    migrated_postgres_url: str,
) -> None:
    database = _database_for(migrated_postgres_url)

    try:
        async with database.sessions() as session:
            loaded = await SqlAlchemyUploadIdempotencyRepository(session).get(
                IdempotencyKey("unknown-key")
            )
    finally:
        await database.dispose()

    assert loaded is None


@pytest.mark.anyio
async def test_maps_a_duplicate_key_to_an_application_error(
    migrated_postgres_url: str,
) -> None:
    database = _database_for(migrated_postgres_url)
    first_document = _document(UUID("23232323-2323-4323-8323-232323232323"))
    first_run = _run(UUID("24242424-2424-4424-8424-242424242424"), first_document.id)
    second_document = _document(UUID("25252525-2525-4525-8525-252525252525"))
    second_run = _run(UUID("26262626-2626-4626-8626-262626262626"), second_document.id)

    try:
        await _add_document_and_run(database, first_document, first_run)
        await _add_document_and_run(database, second_document, second_run)
        async with database.sessions.begin() as session:
            await SqlAlchemyUploadIdempotencyRepository(session).add(
                _record("duplicate-key", first_run.id)
            )

        with pytest.raises(UploadIdempotencyRecordAlreadyExists):
            async with database.sessions.begin() as session:
                await SqlAlchemyUploadIdempotencyRepository(session).add(
                    _record("duplicate-key", second_run.id)
                )
    finally:
        await database.dispose()


@pytest.mark.anyio
async def test_does_not_mask_a_duplicate_processing_run(
    migrated_postgres_url: str,
) -> None:
    database = _database_for(migrated_postgres_url)
    document = _document(UUID("27272727-2727-4727-8727-272727272727"))
    run = _run(UUID("28282828-2828-4828-8828-282828282828"), document.id)

    try:
        await _add_document_and_run(database, document, run)
        async with database.sessions.begin() as session:
            await SqlAlchemyUploadIdempotencyRepository(session).add(_record("first-key", run.id))

        with pytest.raises(IntegrityError):
            async with database.sessions.begin() as session:
                await SqlAlchemyUploadIdempotencyRepository(session).add(
                    _record("second-key", run.id)
                )
    finally:
        await database.dispose()
