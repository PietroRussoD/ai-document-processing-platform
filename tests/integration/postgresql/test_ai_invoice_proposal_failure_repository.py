"""PostgreSQL persistence tests for terminal AI provider failures."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyAiInvoiceProposalFailureRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyProcessingRunRepository,
)
from document_platform.application.ports import InvoiceProposalFailureAlreadyExists
from document_platform.domain.documents import Document
from document_platform.domain.processing import (
    AiInvoiceProposalFailure,
    InvoiceModelProvider,
    InvoiceProposalGenerationFailureCode,
    ProcessingRun,
    ProcessingRunStatus,
)
from document_platform.settings import Settings

AT = datetime(2026, 9, 27, 10, 0, tzinfo=UTC)


@pytest.mark.anyio
@pytest.mark.parametrize("code", list(InvoiceProposalGenerationFailureCode))
async def test_round_trips_failure_without_failing_document(
    migrated_postgres_url: str,
    code: InvoiceProposalGenerationFailureCode,
) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    document_id = uuid4()
    run_id = uuid4()
    document = Document.accept_pdf(
        document_id=document_id,
        original_filename="synthetic-invoice.pdf",
        size_bytes=10_000,
        page_count=1,
        content_sha256=document_id.hex * 2,
        storage_key=f"blobs/{document_id}",
        accepted_at=AT,
    )
    run = ProcessingRun.queue(run_id=run_id, document_id=document_id, queued_at=AT)
    expected = AiInvoiceProposalFailure(
        processing_run_id=run_id,
        provider=InvoiceModelProvider.OLLAMA,
        model_reference="qwen3:8b",
        code=code,
        failed_at=AT,
    )
    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            await SqlAlchemyProcessingRunRepository(session).add(run)
            await SqlAlchemyAiInvoiceProposalFailureRepository(session).add(expected)
        async with database.sessions() as session:
            actual = await SqlAlchemyAiInvoiceProposalFailureRepository(session).get(run_id)
            persisted_run = await SqlAlchemyProcessingRunRepository(session).get(run_id)
    finally:
        await database.dispose()

    assert actual == expected
    assert persisted_run is not None
    assert persisted_run.status is ProcessingRunStatus.QUEUED


@pytest.mark.anyio
async def test_rejects_a_second_failure_for_the_same_run(migrated_postgres_url: str) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    document_id = uuid4()
    run_id = uuid4()
    document = Document.accept_pdf(
        document_id=document_id,
        original_filename="synthetic-invoice.pdf",
        size_bytes=10_000,
        page_count=1,
        content_sha256=document_id.hex * 2,
        storage_key=f"blobs/{document_id}",
        accepted_at=AT,
    )
    run = ProcessingRun.queue(run_id=run_id, document_id=document_id, queued_at=AT)
    failure = AiInvoiceProposalFailure(
        processing_run_id=run_id,
        provider=InvoiceModelProvider.OLLAMA,
        model_reference="qwen3:8b",
        code=InvoiceProposalGenerationFailureCode.TIMEOUT,
        failed_at=AT,
    )
    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            await SqlAlchemyProcessingRunRepository(session).add(run)
            await SqlAlchemyAiInvoiceProposalFailureRepository(session).add(failure)
        with pytest.raises(InvoiceProposalFailureAlreadyExists):
            async with database.sessions.begin() as session:
                await SqlAlchemyAiInvoiceProposalFailureRepository(session).add(failure)
    finally:
        await database.dispose()
