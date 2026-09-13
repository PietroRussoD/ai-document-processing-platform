"""SQLAlchemy document repository integration tests."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.outbound.postgresql.database import Database, create_database
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentRepository,
)
from document_platform.application.ports import (
    ConcurrentDocumentUpdate,
    DocumentAlreadyExists,
)
from document_platform.domain.documents import Document, DocumentStatus
from document_platform.settings import Settings

ACCEPTED_AT = datetime(2026, 9, 13, 10, 0, tzinfo=UTC)


def document_with_id(document_id: UUID) -> Document:
    return Document.accept_pdf(
        document_id=document_id,
        original_filename="supplier-invoice.pdf",
        size_bytes=42_000,
        page_count=2,
        content_sha256=document_id.hex * 2,
        storage_key=f"blobs/{document_id}",
        accepted_at=ACCEPTED_AT,
    )


def database_for(postgres_url: str) -> Database:
    return create_database(Settings(environment="test", database_url=PostgresDsn(postgres_url)))


@pytest.mark.anyio
async def test_adds_and_loads_a_document(migrated_postgres_url: str) -> None:
    database = database_for(migrated_postgres_url)
    document = document_with_id(UUID("11111111-1111-4111-8111-111111111111"))

    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)

        async with database.sessions() as session:
            loaded = await SqlAlchemyDocumentRepository(session).get(document.id)
    finally:
        await database.dispose()

    assert loaded == document


@pytest.mark.anyio
async def test_returns_none_for_an_unknown_document(migrated_postgres_url: str) -> None:
    database = database_for(migrated_postgres_url)

    try:
        async with database.sessions() as session:
            loaded = await SqlAlchemyDocumentRepository(session).get(
                UUID("22222222-2222-4222-8222-222222222222")
            )
    finally:
        await database.dispose()

    assert loaded is None


@pytest.mark.anyio
async def test_rejects_a_duplicate_document(migrated_postgres_url: str) -> None:
    database = database_for(migrated_postgres_url)
    document = document_with_id(UUID("33333333-3333-4333-8333-333333333333"))

    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)

        with pytest.raises(DocumentAlreadyExists):
            async with database.sessions.begin() as session:
                await SqlAlchemyDocumentRepository(session).add(document)
    finally:
        await database.dispose()


@pytest.mark.anyio
async def test_updates_a_document_with_optimistic_locking(migrated_postgres_url: str) -> None:
    database = database_for(migrated_postgres_url)
    document = document_with_id(UUID("44444444-4444-4444-8444-444444444444"))
    processing = document.start_processing(at=ACCEPTED_AT + timedelta(seconds=1))

    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)

        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).update(processing)

        async with database.sessions() as session:
            loaded = await SqlAlchemyDocumentRepository(session).get(document.id)
    finally:
        await database.dispose()

    assert loaded is not None
    assert loaded.status is DocumentStatus.PROCESSING
    assert loaded.version == 1


@pytest.mark.anyio
async def test_rejects_a_stale_document_update(migrated_postgres_url: str) -> None:
    database = database_for(migrated_postgres_url)
    document = document_with_id(UUID("55555555-5555-4555-8555-555555555555"))
    first_update = document.start_processing(at=ACCEPTED_AT + timedelta(seconds=1))
    stale_update = document.start_processing(at=ACCEPTED_AT + timedelta(seconds=2))

    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)

        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).update(first_update)

        with pytest.raises(ConcurrentDocumentUpdate):
            async with database.sessions.begin() as session:
                await SqlAlchemyDocumentRepository(session).update(stale_update)
    finally:
        await database.dispose()
