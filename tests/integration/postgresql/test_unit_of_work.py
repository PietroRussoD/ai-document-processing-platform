"""SQLAlchemy unit-of-work integration tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.outbound.postgresql import SqlAlchemyUnitOfWork
from document_platform.adapters.outbound.postgresql.database import Database, create_database
from document_platform.application.upload_idempotency import (
    IdempotencyKey,
    UploadIdempotencyRecord,
    UploadRequestFingerprint,
)
from document_platform.domain.documents import Document
from document_platform.domain.processing import ProcessingRun
from document_platform.settings import Settings

ACCEPTED_AT = datetime(2026, 9, 13, 11, 0, tzinfo=UTC)


class SimulatedFailure(RuntimeError):
    pass


def database_for(postgres_url: str) -> Database:
    return create_database(Settings(environment="test", database_url=PostgresDsn(postgres_url)))


def document_with_id(document_id: UUID) -> Document:
    return Document.accept_pdf(
        document_id=document_id,
        original_filename="purchase-order.pdf",
        size_bytes=21_000,
        page_count=1,
        content_sha256=document_id.hex * 2,
        storage_key=f"blobs/{document_id}",
        accepted_at=ACCEPTED_AT,
    )


async def load_document(database: Database, document_id: UUID) -> Document | None:
    async with SqlAlchemyUnitOfWork(database.sessions) as unit_of_work:
        return await unit_of_work.documents.get(document_id)


async def load_run(database: Database, run_id: UUID) -> ProcessingRun | None:
    async with SqlAlchemyUnitOfWork(database.sessions) as unit_of_work:
        return await unit_of_work.processing_runs.get(run_id)


async def load_idempotency_record(
    database: Database,
    key: IdempotencyKey,
) -> UploadIdempotencyRecord | None:
    async with SqlAlchemyUnitOfWork(database.sessions) as unit_of_work:
        return await unit_of_work.upload_idempotency.get(key)


@pytest.mark.anyio
async def test_commits_all_work_explicitly(migrated_postgres_url: str) -> None:
    database = database_for(migrated_postgres_url)
    document = document_with_id(UUID("66666666-6666-4666-8666-666666666666"))
    run = ProcessingRun.queue(
        run_id=UUID("69696969-6969-4969-8969-696969696969"),
        document_id=document.id,
        queued_at=ACCEPTED_AT,
    )
    idempotency_record = UploadIdempotencyRecord(
        key=IdempotencyKey("unit-of-work-test"),
        request_fingerprint=UploadRequestFingerprint("a" * 64),
        processing_run_id=run.id,
        recorded_at=ACCEPTED_AT,
    )

    try:
        async with SqlAlchemyUnitOfWork(database.sessions) as unit_of_work:
            await unit_of_work.documents.add(document)
            await unit_of_work.processing_runs.add(run)
            await unit_of_work.upload_idempotency.add(idempotency_record)
            await unit_of_work.commit()

        loaded_document = await load_document(database, document.id)
        loaded_run = await load_run(database, run.id)
        loaded_idempotency_record = await load_idempotency_record(
            database,
            idempotency_record.key,
        )
    finally:
        await database.dispose()

    assert loaded_document == document
    assert loaded_run == run
    assert loaded_idempotency_record == idempotency_record


@pytest.mark.anyio
async def test_rolls_back_when_commit_is_omitted(migrated_postgres_url: str) -> None:
    database = database_for(migrated_postgres_url)
    document = document_with_id(UUID("77777777-7777-4777-8777-777777777777"))

    try:
        async with SqlAlchemyUnitOfWork(database.sessions) as unit_of_work:
            await unit_of_work.documents.add(document)

        loaded = await load_document(database, document.id)
    finally:
        await database.dispose()

    assert loaded is None


@pytest.mark.anyio
async def test_rolls_back_when_the_operation_fails(migrated_postgres_url: str) -> None:
    database = database_for(migrated_postgres_url)
    document = document_with_id(UUID("88888888-8888-4888-8888-888888888888"))

    try:
        with pytest.raises(SimulatedFailure):
            async with SqlAlchemyUnitOfWork(database.sessions) as unit_of_work:
                await unit_of_work.documents.add(document)
                raise SimulatedFailure

        loaded = await load_document(database, document.id)
    finally:
        await database.dispose()

    assert loaded is None


@pytest.mark.anyio
async def test_rejects_operations_outside_the_context(migrated_postgres_url: str) -> None:
    database = database_for(migrated_postgres_url)
    unit_of_work = SqlAlchemyUnitOfWork(database.sessions)

    try:
        with pytest.raises(RuntimeError, match="unit of work is not active"):
            _ = unit_of_work.documents

        with pytest.raises(RuntimeError, match="unit of work is not active"):
            _ = unit_of_work.document_classifications

        with pytest.raises(RuntimeError, match="unit of work is not active"):
            _ = unit_of_work.invoice_extractions

        with pytest.raises(RuntimeError, match="unit of work is not active"):
            _ = unit_of_work.upload_idempotency

        with pytest.raises(RuntimeError, match="unit of work is not active"):
            await unit_of_work.commit()
    finally:
        await database.dispose()
