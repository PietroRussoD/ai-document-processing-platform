"""SQLAlchemy processing-run repository integration tests."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.outbound.postgresql.database import Database, create_database
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyProcessingRunRepository,
)
from document_platform.application.ports import (
    ActiveProcessingRunAlreadyExists,
    ConcurrentProcessingRunUpdate,
    ProcessingRunAlreadyExists,
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

QUEUED_AT = datetime(2026, 9, 13, 14, 0, tzinfo=UTC)


def database_for(postgres_url: str) -> Database:
    return create_database(Settings(environment="test", database_url=PostgresDsn(postgres_url)))


def document_with_id(document_id: UUID) -> Document:
    return Document.accept_pdf(
        document_id=document_id,
        original_filename="repository-test.pdf",
        size_bytes=10_000,
        page_count=1,
        content_sha256=document_id.hex * 2,
        storage_key=f"blobs/{document_id}",
        accepted_at=QUEUED_AT,
    )


def run_with_id(
    run_id: UUID,
    document_id: UUID,
    *,
    previous_run_id: UUID | None = None,
) -> ProcessingRun:
    return ProcessingRun.queue(
        run_id=run_id,
        document_id=document_id,
        queued_at=QUEUED_AT,
        previous_run_id=previous_run_id,
    )


async def add_document(database: Database, document: Document) -> None:
    async with database.sessions.begin() as session:
        await SqlAlchemyDocumentRepository(session).add(document)


@pytest.mark.anyio
async def test_adds_and_loads_a_processing_run(migrated_postgres_url: str) -> None:
    database = database_for(migrated_postgres_url)
    document = document_with_id(UUID("10101010-1010-4010-8010-101010101010"))
    run = run_with_id(UUID("20202020-2020-4020-8020-202020202020"), document.id)

    try:
        await add_document(database, document)
        async with database.sessions.begin() as session:
            await SqlAlchemyProcessingRunRepository(session).add(run)

        async with database.sessions() as session:
            loaded = await SqlAlchemyProcessingRunRepository(session).get(run.id)
    finally:
        await database.dispose()

    assert loaded == run


@pytest.mark.anyio
async def test_adds_and_loads_processing_run_lineage(migrated_postgres_url: str) -> None:
    database = database_for(migrated_postgres_url)
    document = document_with_id(UUID("f1010101-0101-4101-8101-010101010101"))
    source_run = (
        run_with_id(UUID("f2020202-0202-4202-8202-020202020202"), document.id)
        .start(at=QUEUED_AT + timedelta(seconds=1))
        .complete(at=QUEUED_AT + timedelta(seconds=2))
    )
    replacement_run = run_with_id(
        UUID("f3030303-0303-4303-8303-030303030303"),
        document.id,
        previous_run_id=source_run.id,
    )

    try:
        await add_document(database, document)
        async with database.sessions.begin() as session:
            repository = SqlAlchemyProcessingRunRepository(session)
            await repository.add(source_run)
            await repository.add(replacement_run)

        async with database.sessions() as session:
            loaded = await SqlAlchemyProcessingRunRepository(session).get(replacement_run.id)
    finally:
        await database.dispose()

    assert loaded == replacement_run


@pytest.mark.anyio
async def test_adds_and_loads_terminal_failure_evidence(migrated_postgres_url: str) -> None:
    database = database_for(migrated_postgres_url)
    document = document_with_id(UUID("f4040404-0404-4404-8404-040404040404"))
    failed_run = (
        run_with_id(UUID("f5050505-0505-4505-8505-050505050505"), document.id)
        .start(at=QUEUED_AT + timedelta(seconds=1))
        .fail(
            at=QUEUED_AT + timedelta(seconds=2),
            failure=ProcessingFailure(
                stage=ProcessingStage.EMBEDDED_TEXT_EXTRACTION,
                code=ProcessingFailureCode.ACTIVITY_RETRY_EXHAUSTED,
            ),
        )
    )

    try:
        await add_document(database, document)
        async with database.sessions.begin() as session:
            await SqlAlchemyProcessingRunRepository(session).add(failed_run)

        async with database.sessions() as session:
            loaded = await SqlAlchemyProcessingRunRepository(session).get(failed_run.id)
    finally:
        await database.dispose()

    assert loaded == failed_run


@pytest.mark.anyio
async def test_rejects_multiple_active_processing_runs_for_a_document(
    migrated_postgres_url: str,
) -> None:
    database = database_for(migrated_postgres_url)
    document = document_with_id(UUID("34343434-3434-4434-8434-343434343434"))
    first_run = run_with_id(UUID("45454545-4545-4455-8455-454545454545"), document.id)
    second_run = run_with_id(UUID("56565656-5656-4565-8565-565656565656"), document.id)

    try:
        await add_document(database, document)
        async with database.sessions.begin() as session:
            await SqlAlchemyProcessingRunRepository(session).add(first_run)

        with pytest.raises(ActiveProcessingRunAlreadyExists):
            async with database.sessions.begin() as session:
                await SqlAlchemyProcessingRunRepository(session).add(second_run)
    finally:
        await database.dispose()


@pytest.mark.anyio
async def test_returns_none_for_an_unknown_processing_run(
    migrated_postgres_url: str,
) -> None:
    database = database_for(migrated_postgres_url)

    try:
        async with database.sessions() as session:
            loaded = await SqlAlchemyProcessingRunRepository(session).get(
                UUID("30303030-3030-4030-8030-303030303030")
            )
    finally:
        await database.dispose()

    assert loaded is None


@pytest.mark.anyio
async def test_rejects_a_duplicate_processing_run(migrated_postgres_url: str) -> None:
    database = database_for(migrated_postgres_url)
    document = document_with_id(UUID("40404040-4040-4040-8040-404040404040"))
    run = run_with_id(UUID("50505050-5050-4050-8050-505050505050"), document.id)

    try:
        await add_document(database, document)
        async with database.sessions.begin() as session:
            await SqlAlchemyProcessingRunRepository(session).add(run)

        with pytest.raises(ProcessingRunAlreadyExists):
            async with database.sessions.begin() as session:
                await SqlAlchemyProcessingRunRepository(session).add(run)
    finally:
        await database.dispose()


@pytest.mark.anyio
async def test_updates_a_processing_run_with_optimistic_locking(
    migrated_postgres_url: str,
) -> None:
    database = database_for(migrated_postgres_url)
    document = document_with_id(UUID("60606060-6060-4060-8060-606060606060"))
    run = run_with_id(UUID("70707070-7070-4070-8070-707070707070"), document.id)
    running = run.start(at=QUEUED_AT + timedelta(seconds=1))

    try:
        await add_document(database, document)
        async with database.sessions.begin() as session:
            await SqlAlchemyProcessingRunRepository(session).add(run)

        async with database.sessions.begin() as session:
            await SqlAlchemyProcessingRunRepository(session).update(running)

        async with database.sessions() as session:
            loaded = await SqlAlchemyProcessingRunRepository(session).get(run.id)
    finally:
        await database.dispose()

    assert loaded is not None
    assert loaded.status is ProcessingRunStatus.RUNNING
    assert loaded.started_at == running.started_at
    assert loaded.attempt_count == 1
    assert loaded.version == 1


@pytest.mark.anyio
async def test_rejects_a_stale_processing_run_update(migrated_postgres_url: str) -> None:
    database = database_for(migrated_postgres_url)
    document = document_with_id(UUID("80808080-8080-4080-8080-808080808080"))
    run = run_with_id(UUID("90909090-9090-4090-8090-909090909090"), document.id)
    first_update = run.start(at=QUEUED_AT + timedelta(seconds=1))
    stale_update = run.start(at=QUEUED_AT + timedelta(seconds=2))

    try:
        await add_document(database, document)
        async with database.sessions.begin() as session:
            await SqlAlchemyProcessingRunRepository(session).add(run)

        async with database.sessions.begin() as session:
            await SqlAlchemyProcessingRunRepository(session).update(first_update)

        with pytest.raises(ConcurrentProcessingRunUpdate):
            async with database.sessions.begin() as session:
                await SqlAlchemyProcessingRunRepository(session).update(stale_update)
    finally:
        await database.dispose()
