"""SQLAlchemy workflow-start request repository integration tests."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.outbound.postgresql.database import Database, create_database
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyProcessingRunRepository,
    SqlAlchemyWorkflowStartRequestRepository,
)
from document_platform.application.ports import ConcurrentWorkflowStartRequestUpdate
from document_platform.domain.documents import Document
from document_platform.domain.processing import WorkflowStartRequest
from document_platform.domain.processing.processing_run import ProcessingRun
from document_platform.settings import Settings

REQUESTED_AT = datetime(2026, 9, 15, 9, 0, tzinfo=UTC)


def database_for(postgres_url: str) -> Database:
    return create_database(Settings(environment="test", database_url=PostgresDsn(postgres_url)))


async def add_run(database: Database, document_id: UUID, run_id: UUID) -> None:
    document = Document.accept_pdf(
        document_id=document_id,
        original_filename="workflow-request-test.pdf",
        size_bytes=10_000,
        page_count=1,
        content_sha256=document_id.hex * 2,
        storage_key=f"blobs/{document_id}",
        accepted_at=REQUESTED_AT,
    )
    run = ProcessingRun.queue(run_id=run_id, document_id=document_id, queued_at=REQUESTED_AT)
    async with database.sessions.begin() as session:
        await SqlAlchemyDocumentRepository(session).add(document)
        await SqlAlchemyProcessingRunRepository(session).add(run)


@pytest.mark.anyio
async def test_adds_loads_and_marks_a_workflow_start_request(
    migrated_postgres_url: str,
) -> None:
    database = database_for(migrated_postgres_url)
    run_id = UUID("13131313-1313-4131-8131-131313131313")
    request = WorkflowStartRequest.request(processing_run_id=run_id, requested_at=REQUESTED_AT)
    dispatched = request.mark_dispatched(at=REQUESTED_AT + timedelta(seconds=1))

    try:
        await add_run(database, UUID("14141414-1414-4141-8141-141414141414"), run_id)
        async with database.sessions.begin() as session:
            await SqlAlchemyWorkflowStartRequestRepository(session).add(request)

        async with database.sessions() as session:
            loaded = await SqlAlchemyWorkflowStartRequestRepository(session).get(run_id)

        async with database.sessions.begin() as session:
            await SqlAlchemyWorkflowStartRequestRepository(session).update(dispatched)

        async with database.sessions() as session:
            updated = await SqlAlchemyWorkflowStartRequestRepository(session).get(run_id)
    finally:
        await database.dispose()

    assert loaded == request
    assert updated == dispatched


@pytest.mark.anyio
async def test_rejects_a_stale_workflow_start_request_update(
    migrated_postgres_url: str,
) -> None:
    database = database_for(migrated_postgres_url)
    run_id = UUID("15151515-1515-4151-8151-151515151515")
    request = WorkflowStartRequest.request(processing_run_id=run_id, requested_at=REQUESTED_AT)
    first_update = request.mark_dispatched(at=REQUESTED_AT + timedelta(seconds=1))
    stale_update = request.mark_dispatched(at=REQUESTED_AT + timedelta(seconds=2))

    try:
        await add_run(database, UUID("16161616-1616-4161-8161-161616161616"), run_id)
        async with database.sessions.begin() as session:
            await SqlAlchemyWorkflowStartRequestRepository(session).add(request)
        async with database.sessions.begin() as session:
            await SqlAlchemyWorkflowStartRequestRepository(session).update(first_update)

        with pytest.raises(ConcurrentWorkflowStartRequestUpdate):
            async with database.sessions.begin() as session:
                await SqlAlchemyWorkflowStartRequestRepository(session).update(stale_update)
    finally:
        await database.dispose()
