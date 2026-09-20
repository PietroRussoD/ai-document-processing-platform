"""SQLAlchemy reprocessing-operation repository integration tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.outbound.postgresql.database import Database, create_database
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyProcessingRunRepository,
    SqlAlchemyReprocessingOperationRepository,
)
from document_platform.application.ports import ReprocessingOperationAlreadyExists
from document_platform.domain.documents import Document
from document_platform.domain.processing import ProcessingRun, ReprocessingOperation
from document_platform.settings import Settings

REQUESTED_AT = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)


def _database_for(postgres_url: str) -> Database:
    return create_database(Settings(environment="test", database_url=PostgresDsn(postgres_url)))


def _document(document_id: UUID) -> Document:
    return Document.accept_pdf(
        document_id=document_id,
        original_filename="reprocessing-operation-test.pdf",
        size_bytes=1_000,
        page_count=1,
        content_sha256=document_id.hex * 2,
        storage_key=f"blobs/{document_id}",
        accepted_at=REQUESTED_AT,
    )


def _run(run_id: UUID, document_id: UUID, *, previous_run_id: UUID | None = None) -> ProcessingRun:
    return ProcessingRun.queue(
        run_id=run_id,
        document_id=document_id,
        queued_at=REQUESTED_AT,
        previous_run_id=previous_run_id,
    )


def _operation(
    *,
    operation_id: UUID,
    document_id: UUID,
    source_run_id: UUID,
    replacement_run_id: UUID,
    idempotency_key: str,
) -> ReprocessingOperation:
    return ReprocessingOperation.request(
        operation_id=operation_id,
        document_id=document_id,
        source_run_id=source_run_id,
        replacement_run_id=replacement_run_id,
        requested_by="local-review-operator",
        reason="Retry after the upstream outage was resolved.",
        idempotency_key=idempotency_key,
        requested_at=REQUESTED_AT,
    )


async def _add_document_and_runs(
    database: Database,
    document: Document,
    source_run: ProcessingRun,
    replacement_run: ProcessingRun,
) -> None:
    async with database.sessions.begin() as session:
        document_repository = SqlAlchemyDocumentRepository(session)
        run_repository = SqlAlchemyProcessingRunRepository(session)
        await document_repository.add(document)
        await run_repository.add(source_run)
        await run_repository.add(replacement_run)


@pytest.mark.anyio
async def test_adds_and_loads_a_reprocessing_operation(migrated_postgres_url: str) -> None:
    database = _database_for(migrated_postgres_url)
    document = _document(UUID("10101010-1010-4010-8010-101010101010"))
    source_run = _run(UUID("20202020-2020-4020-8020-202020202020"), document.id)
    replacement_run = _run(
        UUID("30303030-3030-4030-8030-303030303030"),
        document.id,
        previous_run_id=source_run.id,
    )
    operation = _operation(
        operation_id=UUID("40404040-4040-4040-8040-404040404040"),
        document_id=document.id,
        source_run_id=source_run.id,
        replacement_run_id=replacement_run.id,
        idempotency_key="repository-test",
    )

    try:
        await _add_document_and_runs(database, document, source_run, replacement_run)
        async with database.sessions.begin() as session:
            await SqlAlchemyReprocessingOperationRepository(session).add(operation)

        async with database.sessions() as session:
            loaded = await SqlAlchemyReprocessingOperationRepository(session).get(
                document_id=document.id,
                idempotency_key="repository-test",
            )
    finally:
        await database.dispose()

    assert loaded == operation


@pytest.mark.anyio
async def test_maps_a_duplicate_document_idempotency_key_to_an_application_error(
    migrated_postgres_url: str,
) -> None:
    database = _database_for(migrated_postgres_url)
    document = _document(UUID("50505050-5050-4050-8050-505050505050"))
    source_run = _run(UUID("60606060-6060-4060-8060-606060606060"), document.id)
    first_replacement = _run(
        UUID("70707070-7070-4070-8070-707070707070"),
        document.id,
        previous_run_id=source_run.id,
    )
    second_replacement = _run(
        UUID("80808080-8080-4080-8080-808080808080"),
        document.id,
        previous_run_id=source_run.id,
    )
    first_operation = _operation(
        operation_id=UUID("90909090-9090-4090-8090-909090909090"),
        document_id=document.id,
        source_run_id=source_run.id,
        replacement_run_id=first_replacement.id,
        idempotency_key="duplicate-key",
    )
    second_operation = _operation(
        operation_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        document_id=document.id,
        source_run_id=source_run.id,
        replacement_run_id=second_replacement.id,
        idempotency_key="duplicate-key",
    )

    try:
        await _add_document_and_runs(database, document, source_run, first_replacement)
        async with database.sessions.begin() as session:
            await SqlAlchemyProcessingRunRepository(session).add(second_replacement)
        async with database.sessions.begin() as session:
            await SqlAlchemyReprocessingOperationRepository(session).add(first_operation)

        with pytest.raises(ReprocessingOperationAlreadyExists):
            async with database.sessions.begin() as session:
                await SqlAlchemyReprocessingOperationRepository(session).add(second_operation)
    finally:
        await database.dispose()
