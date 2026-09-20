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


def _completed_run(
    run_id: UUID,
    document_id: UUID,
    *,
    previous_run_id: UUID | None = None,
) -> ProcessingRun:
    return (
        _run(run_id, document_id, previous_run_id=previous_run_id)
        .start(at=REQUESTED_AT)
        .complete(at=REQUESTED_AT)
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
    document = _document(UUID("a1010101-0101-4101-8101-010101010101"))
    source_run = _completed_run(UUID("a2020202-0202-4202-8202-020202020202"), document.id)
    replacement_run = _run(
        UUID("a3030303-0303-4303-8303-030303030303"),
        document.id,
        previous_run_id=source_run.id,
    )
    operation = _operation(
        operation_id=UUID("a4040404-0404-4404-8404-040404040404"),
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
    document = _document(UUID("b5050505-0505-4505-8505-050505050505"))
    source_run = _completed_run(UUID("b6060606-0606-4606-8606-060606060606"), document.id)
    first_replacement = _completed_run(
        UUID("b7070707-0707-4707-8707-070707070707"),
        document.id,
        previous_run_id=source_run.id,
    )
    second_replacement = _completed_run(
        UUID("b8080808-0808-4808-8808-080808080808"),
        document.id,
        previous_run_id=source_run.id,
    )
    first_operation = _operation(
        operation_id=UUID("b9090909-0909-4909-8909-090909090909"),
        document_id=document.id,
        source_run_id=source_run.id,
        replacement_run_id=first_replacement.id,
        idempotency_key="duplicate-key",
    )
    second_operation = _operation(
        operation_id=UUID("caaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
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
