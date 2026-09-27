"""PostgreSQL persistence tests for immutable AI invoice proposals."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.outbound.postgresql.database import Database, create_database
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyAiInvoiceExtractionProposalRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyProcessingRunRepository,
)
from document_platform.application.ports import InvoiceProposalAlreadyExists
from document_platform.domain.documents import Document
from document_platform.domain.processing import (
    AiInvoiceExtractionProposal,
    InvoiceModelProvider,
    InvoiceProposalField,
    InvoiceProposalIssue,
    InvoiceProposalIssueCode,
    InvoiceProposalStatus,
    ProcessingRun,
)
from document_platform.settings import Settings

AT = datetime(2026, 9, 27, 10, 0, tzinfo=UTC)
DOCUMENT_ID = uuid4()
RUN_ID = uuid4()
TEXT_SHA256 = "a" * 64


def database_for(postgres_url: str) -> Database:
    return create_database(Settings(environment="test", database_url=PostgresDsn(postgres_url)))


def proposal(
    run_id: UUID = RUN_ID,
    status: InvoiceProposalStatus = InvoiceProposalStatus.VALID,
) -> AiInvoiceExtractionProposal:
    invoice_number: str | None = "INV-42"
    issue_date: date | None = date(2026, 9, 27)
    supplier_name: str | None = "Acme Ltd"
    currency: str | None = "EUR"
    total_amount: Decimal | None = Decimal("12.5000")
    issues: tuple[InvoiceProposalIssue, ...] = ()
    if status is InvoiceProposalStatus.PARTIAL:
        invoice_number = None
        issues = (
            InvoiceProposalIssue(
                InvoiceProposalIssueCode.MISSING_FIELD,
                InvoiceProposalField.INVOICE_NUMBER,
            ),
        )
    elif status is InvoiceProposalStatus.INVALID:
        invoice_number = None
        issue_date = None
        supplier_name = None
        currency = None
        total_amount = None
        issues = (InvoiceProposalIssue(InvoiceProposalIssueCode.MALFORMED_RESPONSE, None),)
    return AiInvoiceExtractionProposal(
        processing_run_id=run_id,
        schema_version=1,
        provider=InvoiceModelProvider.OLLAMA,
        model_reference="qwen2.5:3b",
        model_digest="b" * 64,
        prompt_version="invoice-v1",
        selected_text_sha256=TEXT_SHA256,
        status=status,
        invoice_number=invoice_number,
        issue_date=issue_date,
        supplier_name=supplier_name,
        currency=currency,
        total_amount=total_amount,
        issues=issues,
        proposed_at=AT,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "status",
    [
        InvoiceProposalStatus.VALID,
        InvoiceProposalStatus.PARTIAL,
        InvoiceProposalStatus.INVALID,
    ],
)
async def test_round_trips_proposals_with_each_status(
    migrated_postgres_url: str,
    status: InvoiceProposalStatus,
) -> None:
    database = database_for(migrated_postgres_url)
    run_id = UUID(int=RUN_ID.int + list(InvoiceProposalStatus).index(status))
    document_id = UUID(int=DOCUMENT_ID.int + list(InvoiceProposalStatus).index(status))
    document = Document.accept_pdf(
        document_id=document_id,
        original_filename="ai-proposal-test.pdf",
        size_bytes=10_000,
        page_count=1,
        content_sha256=document_id.hex * 2,
        storage_key=f"blobs/{document_id}",
        accepted_at=AT,
    )
    run = ProcessingRun.queue(run_id=run_id, document_id=document_id, queued_at=AT)
    expected = proposal(run_id=run_id, status=status)
    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            await SqlAlchemyProcessingRunRepository(session).add(run)
            await SqlAlchemyAiInvoiceExtractionProposalRepository(session).add(expected)
        async with database.sessions() as session:
            actual = await SqlAlchemyAiInvoiceExtractionProposalRepository(session).get(run_id)
    finally:
        await database.dispose()

    assert actual == expected


@pytest.mark.anyio
async def test_rejects_a_second_proposal_for_the_same_processing_run(
    migrated_postgres_url: str,
) -> None:
    database = database_for(migrated_postgres_url)
    document_id = UUID(int=DOCUMENT_ID.int + 10)
    run_id = UUID(int=RUN_ID.int + 10)
    document = Document.accept_pdf(
        document_id=document_id,
        original_filename="ai-proposal-duplicate-test.pdf",
        size_bytes=10_000,
        page_count=1,
        content_sha256=document_id.hex * 2,
        storage_key=f"blobs/{document_id}",
        accepted_at=AT,
    )
    run = ProcessingRun.queue(run_id=run_id, document_id=document_id, queued_at=AT)
    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            await SqlAlchemyProcessingRunRepository(session).add(run)
            await SqlAlchemyAiInvoiceExtractionProposalRepository(session).add(
                proposal(run_id=run_id)
            )
        with pytest.raises(InvoiceProposalAlreadyExists):
            async with database.sessions.begin() as session:
                await SqlAlchemyAiInvoiceExtractionProposalRepository(session).add(
                    proposal(run_id=run_id)
                )
    finally:
        await database.dispose()
