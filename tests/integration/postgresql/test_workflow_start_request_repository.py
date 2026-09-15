"""SQLAlchemy workflow-start request repository integration tests."""

import asyncio
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
    claimed = request.claim(
        owner="dispatcher-a",
        token=UUID("17171717-1717-4171-8171-171717171717"),
        at=REQUESTED_AT + timedelta(seconds=1),
        lease_duration=timedelta(seconds=30),
    )
    assert claimed.dispatch_token is not None
    dispatched = claimed.mark_dispatched(
        token=claimed.dispatch_token,
        at=REQUESTED_AT + timedelta(seconds=2),
    )

    try:
        await add_run(database, UUID("14141414-1414-4141-8141-141414141414"), run_id)
        async with database.sessions.begin() as session:
            await SqlAlchemyWorkflowStartRequestRepository(session).add(request)

        async with database.sessions() as session:
            loaded = await SqlAlchemyWorkflowStartRequestRepository(session).get(run_id)

        async with database.sessions.begin() as session:
            await SqlAlchemyWorkflowStartRequestRepository(session).update(claimed)

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
    first_update = request.claim(
        owner="dispatcher-a",
        token=UUID("18181818-1818-4181-8181-181818181818"),
        at=REQUESTED_AT + timedelta(seconds=1),
        lease_duration=timedelta(seconds=30),
    )
    assert first_update.dispatch_token is not None
    stale_update = request.claim(
        owner="dispatcher-b",
        token=UUID("19191919-1919-4191-8191-191919191919"),
        at=REQUESTED_AT + timedelta(seconds=1),
        lease_duration=timedelta(seconds=30),
    )

    try:
        await add_run(database, UUID("16161616-1616-4161-8161-161616161616"), run_id)
        async with database.sessions.begin() as session:
            await SqlAlchemyWorkflowStartRequestRepository(session).add(request)
        async with database.sessions.begin() as session:
            await SqlAlchemyWorkflowStartRequestRepository(session).update(first_update)

        with pytest.raises(ConcurrentWorkflowStartRequestUpdate):
            async with database.sessions.begin() as session:
                await SqlAlchemyWorkflowStartRequestRepository(session).update(stale_update)

        async with database.sessions.begin() as session:
            await SqlAlchemyWorkflowStartRequestRepository(session).update(
                first_update.mark_dispatched(
                    token=first_update.dispatch_token,
                    at=REQUESTED_AT + timedelta(seconds=2),
                )
            )
    finally:
        await database.dispose()


@pytest.mark.anyio
async def test_claims_disjoint_requests_and_recovers_an_expired_claim(
    migrated_postgres_url: str,
) -> None:
    database = database_for(migrated_postgres_url)
    run_ids = (
        UUID("a0a0a0a0-a0a0-40a0-80a0-a0a0a0a0a0a0"),
        UUID("a1a1a1a1-a1a1-41a1-81a1-a1a1a1a1a1a1"),
        UUID("a2a2a2a2-a2a2-42a2-82a2-a2a2a2a2a2a2"),
        UUID("a3a3a3a3-a3a3-43a3-83a3-a3a3a3a3a3a3"),
    )
    document_ids = (
        UUID("b0b0b0b0-b0b0-40b0-80b0-b0b0b0b0b0b0"),
        UUID("b1b1b1b1-b1b1-41b1-81b1-b1b1b1b1b1b1"),
        UUID("b2b2b2b2-b2b2-42b2-82b2-b2b2b2b2b2b2"),
        UUID("b3b3b3b3-b3b3-43b3-83b3-b3b3b3b3b3b3"),
    )

    async def claim(
        owner: str,
        claim_tokens: tuple[UUID, UUID],
    ) -> tuple[WorkflowStartRequest, ...]:
        tokens = iter(claim_tokens)
        async with database.sessions.begin() as session:
            return await SqlAlchemyWorkflowStartRequestRepository(session).claim_pending(
                owner=owner,
                claimed_at=REQUESTED_AT + timedelta(seconds=1),
                lease_duration=timedelta(seconds=30),
                limit=2,
                token_generator=lambda: next(tokens),
            )

    try:
        for document_id, run_id in zip(document_ids, run_ids, strict=True):
            await add_run(database, document_id, run_id)
            async with database.sessions.begin() as session:
                await SqlAlchemyWorkflowStartRequestRepository(session).add(
                    WorkflowStartRequest.request(
                        processing_run_id=run_id,
                        requested_at=REQUESTED_AT,
                    )
                )

        first_claim, second_claim = await asyncio.gather(
            claim(
                "dispatcher-a",
                (
                    UUID("c0c0c0c0-c0c0-40c0-80c0-c0c0c0c0c0c0"),
                    UUID("c1c1c1c1-c1c1-41c1-81c1-c1c1c1c1c1c1"),
                ),
            ),
            claim(
                "dispatcher-b",
                (
                    UUID("c2c2c2c2-c2c2-42c2-82c2-c2c2c2c2c2c2"),
                    UUID("c3c3c3c3-c3c3-43c3-83c3-c3c3c3c3c3c3"),
                ),
            ),
        )

        async with database.sessions.begin() as session:
            recovered = await SqlAlchemyWorkflowStartRequestRepository(session).claim_pending(
                owner="dispatcher-c",
                claimed_at=REQUESTED_AT + timedelta(seconds=32),
                lease_duration=timedelta(seconds=30),
                limit=1,
                token_generator=lambda: UUID("c4c4c4c4-c4c4-44c4-84c4-c4c4c4c4c4c4"),
            )
    finally:
        await database.dispose()

    claimed_ids = {request.processing_run_id for request in first_claim + second_claim}
    assert len(first_claim) == 2
    assert len(second_claim) == 2
    assert claimed_ids == set(run_ids)
    assert len(recovered) == 1
    assert recovered[0].processing_run_id == run_ids[0]
    assert recovered[0].attempt_count == 2
