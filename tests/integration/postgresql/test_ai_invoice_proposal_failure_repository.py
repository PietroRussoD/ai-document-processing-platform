"""PostgreSQL persistence tests for terminal AI provider failures."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyAiInvoiceExtractionProposalRepository,
    SqlAlchemyAiInvoiceProposalFailureRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyProcessingRunRepository,
)
from document_platform.application.ports import (
    InvoiceProposalFailureAlreadyExists,
    InvoiceProposalOutcomeConflict,
)
from document_platform.domain.documents import Document
from document_platform.domain.processing import (
    AiInvoiceExtractionProposal,
    AiInvoiceProposalFailure,
    InvoiceModelProvider,
    InvoiceProposalGenerationFailureCode,
    InvoiceProposalStatus,
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


@pytest.mark.anyio
@pytest.mark.parametrize("first_outcome", ["proposal", "failure"])
async def test_rejects_both_outcomes_for_the_same_run(
    migrated_postgres_url: str,
    first_outcome: str,
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
    proposal = AiInvoiceExtractionProposal(
        processing_run_id=run_id,
        schema_version=1,
        provider=InvoiceModelProvider.OLLAMA,
        model_reference="qwen3:8b",
        model_digest=None,
        prompt_version="invoice-fields-v1",
        selected_text_sha256="a" * 64,
        status=InvoiceProposalStatus.VALID,
        invoice_number="INV-42",
        issue_date=date(2026, 9, 27),
        supplier_name="Synthetic Supplier",
        currency="EUR",
        total_amount=Decimal("12.50"),
        issues=(),
        proposed_at=AT,
    )
    failure = AiInvoiceProposalFailure(
        processing_run_id=run_id,
        provider=InvoiceModelProvider.OLLAMA,
        model_reference="qwen3:8b",
        code=InvoiceProposalGenerationFailureCode.UNAVAILABLE,
        failed_at=AT,
    )
    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            await SqlAlchemyProcessingRunRepository(session).add(run)
            if first_outcome == "proposal":
                await SqlAlchemyAiInvoiceExtractionProposalRepository(session).add(proposal)
            else:
                await SqlAlchemyAiInvoiceProposalFailureRepository(session).add(failure)
        with pytest.raises(InvoiceProposalOutcomeConflict):
            async with database.sessions.begin() as session:
                if first_outcome == "proposal":
                    await SqlAlchemyAiInvoiceProposalFailureRepository(session).add(failure)
                else:
                    await SqlAlchemyAiInvoiceExtractionProposalRepository(session).add(proposal)
    finally:
        await database.dispose()
