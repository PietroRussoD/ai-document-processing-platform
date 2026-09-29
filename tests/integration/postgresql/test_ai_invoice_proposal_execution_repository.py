"""Real PostgreSQL lifecycle, constraint and concurrency checks."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import PostgresDsn
from sqlalchemy import delete, text
from sqlalchemy.exc import IntegrityError

from document_platform.adapters.outbound.postgresql import SqlAlchemyUnitOfWork
from document_platform.adapters.outbound.postgresql.database import Database, create_database
from document_platform.adapters.outbound.postgresql.models import (
    AiInvoiceProposalExecutionRecord,
    DocumentRecord,
)
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyAiInvoiceProposalExecutionRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyProcessingRunRepository,
)
from document_platform.application.commands import (
    ProposeInvoiceFields,
    ProposeInvoiceFieldsHandler,
    RecordInvoiceProposalFailure,
    RecordInvoiceProposalFailureHandler,
)
from document_platform.application.ports import InvoiceProposalRequest
from document_platform.application.ports.invoice_proposal_execution_repository import (
    AiInvoiceProposalExecutionAlreadyExists,
    ConcurrentAiInvoiceProposalExecutionUpdate,
    InvoiceProposalExecutionRepository,
)
from document_platform.domain.documents import Document
from document_platform.domain.processing import (
    AiInvoiceExtractionProposal,
    AiInvoiceProposalExecution,
    AiInvoiceProposalExecutionStatus,
    BusinessDocumentType,
    DocumentClassification,
    DocumentClassificationReason,
    DocumentTextExtraction,
    DocumentTextSelection,
    EmbeddedTextQuality,
    InvalidAiInvoiceProposalExecutionTransition,
    InvoiceModelProvider,
    InvoiceProposalGenerationFailureCode,
    InvoiceProposalIssue,
    InvoiceProposalIssueCode,
    InvoiceProposalStatus,
    ProcessingRun,
    ProcessingRunStatus,
    ProcessingTextSelectionReason,
    ProcessingTextSource,
    TextExtractionMethod,
)
from document_platform.settings import Settings

AT = datetime(2026, 9, 29, 10, tzinfo=UTC)
LATER = AT + timedelta(seconds=30)


@pytest.fixture
async def execution_database(
    migrated_postgres_url: str,
) -> AsyncIterator[tuple[Database, UUID, UUID]]:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    document_id, run_id = uuid4(), uuid4()
    document = Document.accept_pdf(
        document_id=document_id,
        original_filename="synthetic-execution.pdf",
        size_bytes=100,
        page_count=1,
        content_sha256=document_id.hex * 2,
        storage_key=f"blobs/{document_id}",
        accepted_at=AT,
    )
    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            await SqlAlchemyProcessingRunRepository(session).add(
                ProcessingRun.queue(run_id=run_id, document_id=document_id, queued_at=AT)
            )
        yield database, run_id, document_id
    finally:
        await database.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize("enabled", [False, True])
async def test_round_trips_initial_state_without_changing_run(
    execution_database: tuple[Database, UUID, UUID], enabled: bool
) -> None:
    database, run_id, _ = execution_database
    expected = AiInvoiceProposalExecution.begin(processing_run_id=run_id, enabled=enabled, at=AT)
    async with database.sessions.begin() as session:
        repository: InvoiceProposalExecutionRepository = (
            SqlAlchemyAiInvoiceProposalExecutionRepository(session)
        )
        await repository.add(expected)
    async with database.sessions() as session:
        actual = await SqlAlchemyAiInvoiceProposalExecutionRepository(session).get(run_id)
        run = await SqlAlchemyProcessingRunRepository(session).get(run_id)
    assert actual == expected
    assert run is not None and run.status is ProcessingRunStatus.QUEUED


@pytest.mark.anyio
async def test_absent_execution_remains_unknown(
    execution_database: tuple[Database, UUID, UUID],
) -> None:
    database, run_id, _ = execution_database
    async with database.sessions() as session:
        assert await SqlAlchemyAiInvoiceProposalExecutionRepository(session).get(run_id) is None


@pytest.mark.anyio
async def test_rejects_duplicate_execution(
    execution_database: tuple[Database, UUID, UUID],
) -> None:
    database, run_id, _ = execution_database
    execution = AiInvoiceProposalExecution.begin(processing_run_id=run_id, enabled=True, at=AT)
    async with database.sessions.begin() as session:
        await SqlAlchemyAiInvoiceProposalExecutionRepository(session).add(execution)
    with pytest.raises(AiInvoiceProposalExecutionAlreadyExists):
        async with database.sessions.begin() as session:
            await SqlAlchemyAiInvoiceProposalExecutionRepository(session).add(execution)


@pytest.mark.anyio
@pytest.mark.parametrize("failed", [False, True])
async def test_finishes_running_execution(
    execution_database: tuple[Database, UUID, UUID], failed: bool
) -> None:
    database, run_id, _ = execution_database
    execution = AiInvoiceProposalExecution.begin(processing_run_id=run_id, enabled=True, at=AT)
    expected = execution.fail(at=LATER) if failed else execution.complete(at=LATER)
    async with database.sessions.begin() as session:
        await SqlAlchemyAiInvoiceProposalExecutionRepository(session).add(execution)
    async with database.sessions.begin() as session:
        await SqlAlchemyAiInvoiceProposalExecutionRepository(session).finish(expected)
    async with database.sessions() as session:
        assert await SqlAlchemyAiInvoiceProposalExecutionRepository(session).get(run_id) == expected


@pytest.mark.anyio
@pytest.mark.parametrize(
    "initial", ["missing", "disabled", "completed", "failed", "different_start"]
)
async def test_rejects_stale_or_terminal_completion(
    execution_database: tuple[Database, UUID, UUID], initial: str
) -> None:
    database, run_id, _ = execution_database
    execution = AiInvoiceProposalExecution.begin(processing_run_id=run_id, enabled=True, at=AT)
    if initial != "missing":
        stored = AiInvoiceProposalExecution.begin(
            processing_run_id=run_id,
            enabled=initial != "disabled",
            at=LATER if initial == "different_start" else AT,
        )
        async with database.sessions.begin() as session:
            repository = SqlAlchemyAiInvoiceProposalExecutionRepository(session)
            await repository.add(stored)
            if initial == "completed":
                await repository.finish(stored.complete(at=LATER))
            elif initial == "failed":
                await repository.finish(stored.fail(at=LATER))
    with pytest.raises(ConcurrentAiInvoiceProposalExecutionUpdate):
        async with database.sessions.begin() as session:
            await SqlAlchemyAiInvoiceProposalExecutionRepository(session).finish(
                execution.complete(at=LATER)
            )


@pytest.mark.anyio
async def test_only_one_concurrent_terminal_update_succeeds(
    execution_database: tuple[Database, UUID, UUID],
) -> None:
    database, run_id, _ = execution_database
    execution = AiInvoiceProposalExecution.begin(processing_run_id=run_id, enabled=True, at=AT)
    async with database.sessions.begin() as session:
        await SqlAlchemyAiInvoiceProposalExecutionRepository(session).add(execution)

    async def finish(outcome: AiInvoiceProposalExecution) -> bool:
        try:
            async with database.sessions.begin() as session:
                await SqlAlchemyAiInvoiceProposalExecutionRepository(session).finish(outcome)
        except ConcurrentAiInvoiceProposalExecutionUpdate:
            return False
        return True

    outcomes = await asyncio.gather(
        finish(execution.complete(at=LATER)), finish(execution.fail(at=LATER))
    )
    assert sorted(outcomes) == [False, True]
    async with database.sessions() as session:
        actual = await SqlAlchemyAiInvoiceProposalExecutionRepository(session).get(run_id)
    assert actual in (execution.complete(at=LATER), execution.fail(at=LATER))


@pytest.mark.anyio
@pytest.mark.parametrize("failed", [False, True])
async def test_cannot_insert_terminal_state_directly(
    execution_database: tuple[Database, UUID, UUID], failed: bool
) -> None:
    database, run_id, _ = execution_database
    execution = AiInvoiceProposalExecution.begin(processing_run_id=run_id, enabled=True, at=AT)
    terminal = execution.fail(at=LATER) if failed else execution.complete(at=LATER)
    with pytest.raises(ValueError, match="new execution"):
        async with database.sessions.begin() as session:
            await SqlAlchemyAiInvoiceProposalExecutionRepository(session).add(terminal)


@pytest.mark.anyio
@pytest.mark.parametrize("enabled", [False, True])
async def test_finish_requires_terminal_outcome(
    execution_database: tuple[Database, UUID, UUID], enabled: bool
) -> None:
    database, run_id, _ = execution_database
    execution = AiInvoiceProposalExecution.begin(processing_run_id=run_id, enabled=enabled, at=AT)
    with pytest.raises(ValueError, match="completion requires"):
        async with database.sessions.begin() as session:
            await SqlAlchemyAiInvoiceProposalExecutionRepository(session).finish(execution)


@pytest.mark.anyio
async def test_rolls_back_uncommitted_execution(
    execution_database: tuple[Database, UUID, UUID],
) -> None:
    database, run_id, _ = execution_database
    execution = AiInvoiceProposalExecution.begin(processing_run_id=run_id, enabled=True, at=AT)
    async with database.sessions() as session:
        await SqlAlchemyAiInvoiceProposalExecutionRepository(session).add(execution)
        await session.rollback()
    async with database.sessions() as session:
        assert await SqlAlchemyAiInvoiceProposalExecutionRepository(session).get(run_id) is None


@pytest.mark.anyio
async def test_cascades_document_deletion(
    execution_database: tuple[Database, UUID, UUID],
) -> None:
    database, run_id, document_id = execution_database
    async with database.sessions.begin() as session:
        await SqlAlchemyAiInvoiceProposalExecutionRepository(session).add(
            AiInvoiceProposalExecution.begin(processing_run_id=run_id, enabled=False, at=AT)
        )
    async with database.sessions.begin() as session:
        await session.execute(delete(DocumentRecord).where(DocumentRecord.id == document_id))
    async with database.sessions() as session:
        assert await SqlAlchemyAiInvoiceProposalExecutionRepository(session).get(run_id) is None


@pytest.mark.anyio
async def test_rejects_unknown_processing_run(
    execution_database: tuple[Database, UUID, UUID],
) -> None:
    database, _, _ = execution_database
    with pytest.raises(IntegrityError):
        async with database.sessions.begin() as session:
            await SqlAlchemyAiInvoiceProposalExecutionRepository(session).add(
                AiInvoiceProposalExecution.begin(processing_run_id=uuid4(), enabled=True, at=AT)
            )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "status,started_at,finished_at",
    [
        ("UNKNOWN", None, AT),
        ("DISABLED", AT, AT),
        ("DISABLED", None, None),
        ("DISABLED", None, LATER),
        ("RUNNING", None, None),
        ("RUNNING", LATER, None),
        ("RUNNING", AT, AT),
        ("COMPLETED", None, AT),
        ("COMPLETED", AT, None),
        ("COMPLETED", AT, LATER),
        ("COMPLETED", LATER, AT),
        ("FAILED", None, AT),
        ("FAILED", AT, None),
    ],
)
async def test_database_rejects_invalid_lifecycle_metadata(
    execution_database: tuple[Database, UUID, UUID],
    status: str,
    started_at: datetime | None,
    finished_at: datetime | None,
) -> None:
    database, run_id, _ = execution_database
    with pytest.raises(IntegrityError):
        async with database.sessions.begin() as session:
            session.add(
                AiInvoiceProposalExecutionRecord(
                    processing_run_id=run_id,
                    status=status,
                    status_changed_at=AT,
                    started_at=started_at,
                    finished_at=finished_at,
                )
            )
            await session.flush()


@pytest.mark.anyio
async def test_creates_only_execution_columns(
    execution_database: tuple[Database, UUID, UUID],
) -> None:
    database, _, _ = execution_database
    async with database.sessions() as session:
        columns = await session.scalars(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'ai_invoice_proposal_executions'"
            )
        )
    assert set(columns) == {
        "processing_run_id",
        "status",
        "status_changed_at",
        "started_at",
        "finished_at",
    }


class InvalidProposalGenerator:
    async def generate(self, request: InvoiceProposalRequest) -> AiInvoiceExtractionProposal:
        return AiInvoiceExtractionProposal(
            processing_run_id=request.processing_run_id,
            schema_version=1,
            provider=InvoiceModelProvider.OLLAMA,
            model_reference="synthetic-test-model",
            model_digest=None,
            prompt_version="invoice-fields-v1",
            selected_text_sha256=request.selected_text_sha256,
            status=InvoiceProposalStatus.INVALID,
            invoice_number=None,
            issue_date=None,
            supplier_name=None,
            currency=None,
            total_amount=None,
            issues=(InvoiceProposalIssue(InvoiceProposalIssueCode.MALFORMED_RESPONSE, None),),
            proposed_at=AT,
        )


def proposer(database: Database) -> ProposeInvoiceFieldsHandler:
    return ProposeInvoiceFieldsHandler(
        unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(database.sessions),
        proposal_generator=InvalidProposalGenerator(),
        clock=lambda: AT,
    )


async def seed_invoice_text(database: Database, run_id: UUID) -> None:
    async with SqlAlchemyUnitOfWork(database.sessions) as unit_of_work:
        await unit_of_work.document_classifications.add(
            DocumentClassification(
                processing_run_id=run_id,
                document_type=BusinessDocumentType.INVOICE,
                reason=DocumentClassificationReason.KEYWORD_MATCHED,
                classified_at=AT,
            )
        )
        await unit_of_work.document_text_extractions.add(
            DocumentTextExtraction(
                processing_run_id=run_id,
                method=TextExtractionMethod.PYMUPDF,
                text="Synthetic invoice",
                page_count=1,
                character_count=17,
                non_whitespace_character_count=16,
                quality=EmbeddedTextQuality.SUFFICIENT,
                extracted_at=AT,
            )
        )
        await unit_of_work.document_text_selections.add(
            DocumentTextSelection(
                processing_run_id=run_id,
                source=ProcessingTextSource.EMBEDDED,
                reason=ProcessingTextSelectionReason.EMBEDDED_SUFFICIENT,
                selected_at=AT,
            )
        )
        await unit_of_work.commit()


@pytest.mark.anyio
async def test_application_commits_invalid_proposal_and_completed_execution_together(
    execution_database: tuple[Database, UUID, UUID],
) -> None:
    database, run_id, _ = execution_database
    await seed_invoice_text(database, run_id)
    handler = proposer(database)
    assert await handler.begin_execution(ProposeInvoiceFields(run_id), enabled=True)

    result = await handler(ProposeInvoiceFields(run_id))

    async with SqlAlchemyUnitOfWork(database.sessions) as unit_of_work:
        proposal = await unit_of_work.invoice_proposals.get(run_id)
        execution = await unit_of_work.invoice_proposal_executions.get(run_id)
        run = await unit_of_work.processing_runs.get(run_id)
    assert proposal == result.proposal
    assert proposal is not None
    assert proposal.status is InvoiceProposalStatus.INVALID
    assert execution is not None and execution.status is AiInvoiceProposalExecutionStatus.COMPLETED
    assert run is not None and run.status is ProcessingRunStatus.QUEUED
    assert not await handler.begin_execution(ProposeInvoiceFields(run_id), enabled=True)


@pytest.mark.anyio
async def test_application_rolls_back_proposal_if_execution_cannot_finish(
    execution_database: tuple[Database, UUID, UUID],
) -> None:
    database, run_id, _ = execution_database
    await seed_invoice_text(database, run_id)
    handler = proposer(database)
    assert not await handler.begin_execution(ProposeInvoiceFields(run_id), enabled=False)

    with pytest.raises(InvalidAiInvoiceProposalExecutionTransition):
        await handler(ProposeInvoiceFields(run_id))

    async with SqlAlchemyUnitOfWork(database.sessions) as unit_of_work:
        assert await unit_of_work.invoice_proposals.get(run_id) is None
        execution = await unit_of_work.invoice_proposal_executions.get(run_id)
    assert execution is not None and execution.status is AiInvoiceProposalExecutionStatus.DISABLED


@pytest.mark.anyio
@pytest.mark.parametrize("disabled", [False, True])
async def test_application_failure_and_execution_are_atomic(
    execution_database: tuple[Database, UUID, UUID],
    disabled: bool,
) -> None:
    database, run_id, _ = execution_database
    await proposer(database).begin_execution(ProposeInvoiceFields(run_id), enabled=not disabled)
    handler = RecordInvoiceProposalFailureHandler(
        unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(database.sessions),
        clock=lambda: LATER,
    )
    command = RecordInvoiceProposalFailure(
        processing_run_id=run_id,
        provider=InvoiceModelProvider.OLLAMA,
        model_reference="synthetic-test-model",
        code=InvoiceProposalGenerationFailureCode.TIMEOUT,
    )
    if disabled:
        with pytest.raises(InvalidAiInvoiceProposalExecutionTransition):
            await handler(command)
    else:
        await handler(command)
        assert (await handler(command)).replayed

    async with SqlAlchemyUnitOfWork(database.sessions) as unit_of_work:
        failure = await unit_of_work.invoice_proposal_failures.get(run_id)
        execution = await unit_of_work.invoice_proposal_executions.get(run_id)
        run = await unit_of_work.processing_runs.get(run_id)
    assert (failure is None) is disabled
    assert execution is not None
    assert execution.status is (
        AiInvoiceProposalExecutionStatus.DISABLED
        if disabled
        else AiInvoiceProposalExecutionStatus.FAILED
    )
    assert run is not None and run.status is ProcessingRunStatus.QUEUED


@pytest.mark.anyio
async def test_concurrent_application_initialization_preserves_one_start(
    execution_database: tuple[Database, UUID, UUID],
) -> None:
    database, run_id, _ = execution_database
    handler = proposer(database)
    outcomes = await asyncio.gather(
        handler.begin_execution(ProposeInvoiceFields(run_id), enabled=True),
        handler.begin_execution(ProposeInvoiceFields(run_id), enabled=True),
    )
    assert outcomes == [True, True]
    async with SqlAlchemyUnitOfWork(database.sessions) as unit_of_work:
        assert await unit_of_work.invoice_proposal_executions.get(run_id) == (
            AiInvoiceProposalExecution.begin(processing_run_id=run_id, enabled=True, at=AT)
        )
