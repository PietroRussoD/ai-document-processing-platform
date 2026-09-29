"""Terminal provider failure recording tests."""

from datetime import UTC, datetime
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from document_platform.application.commands import (
    InvoiceProposalFailureRecorded,
    RecordInvoiceProposalFailure,
    RecordInvoiceProposalFailureHandler,
)
from document_platform.application.ports import InvoiceProposalOutcomeConflict, UnitOfWork
from document_platform.domain.processing import (
    AiInvoiceProposalExecution,
    AiInvoiceProposalExecutionStatus,
    AiInvoiceProposalFailure,
    InvoiceModelProvider,
    InvoiceProposalGenerationFailureCode,
)

RUN_ID = UUID("d7d7d7d7-d7d7-47d7-87d7-d7d7d7d7d7d7")
AT = datetime(2026, 9, 27, 15, 0, tzinfo=UTC)


class RecordingFailureRepository:
    def __init__(self) -> None:
        self.value: AiInvoiceProposalFailure | None = None

    async def get(self, processing_run_id: UUID) -> AiInvoiceProposalFailure | None:
        return self.value

    async def add(self, failure: AiInvoiceProposalFailure) -> None:
        self.value = failure


class RecordingUnitOfWork:
    def __init__(self) -> None:
        self.invoice_proposal_failures = RecordingFailureRepository()
        self.invoice_proposal_executions = RecordingExecutionRepository()
        self.commit_count = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    async def commit(self) -> None:
        self.commit_count += 1


class RecordingExecutionRepository:
    def __init__(self) -> None:
        self.value: AiInvoiceProposalExecution | None = None

    async def get(self, processing_run_id: UUID) -> AiInvoiceProposalExecution | None:
        return self.value

    async def finish(self, execution: AiInvoiceProposalExecution) -> None:
        self.value = execution


def handler(unit_of_work: RecordingUnitOfWork) -> RecordInvoiceProposalFailureHandler:
    return RecordInvoiceProposalFailureHandler(
        unit_of_work_factory=lambda: cast(UnitOfWork, unit_of_work),
        clock=lambda: AT,
    )


def command(
    code: InvoiceProposalGenerationFailureCode = InvoiceProposalGenerationFailureCode.TIMEOUT,
) -> RecordInvoiceProposalFailure:
    return RecordInvoiceProposalFailure(
        processing_run_id=RUN_ID,
        provider=InvoiceModelProvider.OLLAMA,
        model_reference="qwen3:8b",
        code=code,
    )


@pytest.mark.anyio
async def test_persists_a_safe_terminal_failure_once() -> None:
    unit_of_work = RecordingUnitOfWork()

    result = await handler(unit_of_work)(command())

    assert result == InvoiceProposalFailureRecorded(
        failure=AiInvoiceProposalFailure(
            processing_run_id=RUN_ID,
            provider=InvoiceModelProvider.OLLAMA,
            model_reference="qwen3:8b",
            code=InvoiceProposalGenerationFailureCode.TIMEOUT,
            failed_at=AT,
        ),
        replayed=False,
    )
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_replays_the_same_failure_without_writing_again() -> None:
    unit_of_work = RecordingUnitOfWork()
    recorder = handler(unit_of_work)
    first = await recorder(command())

    result = await recorder(command())

    assert result == InvoiceProposalFailureRecorded(first.failure, replayed=True)
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_rejects_a_different_terminal_failure_for_the_same_run() -> None:
    unit_of_work = RecordingUnitOfWork()
    recorder = handler(unit_of_work)
    await recorder(command())

    with pytest.raises(InvoiceProposalOutcomeConflict):
        await recorder(command(InvoiceProposalGenerationFailureCode.UNAVAILABLE))

    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_failure_and_execution_finish_share_one_commit() -> None:
    unit_of_work = RecordingUnitOfWork()
    unit_of_work.invoice_proposal_executions.value = AiInvoiceProposalExecution.begin(
        processing_run_id=RUN_ID, enabled=True, at=AT
    )

    await handler(unit_of_work)(command())

    execution = unit_of_work.invoice_proposal_executions.value
    assert execution is not None
    assert execution.status is AiInvoiceProposalExecutionStatus.FAILED
    assert execution.finished_at == AT
    assert unit_of_work.invoice_proposal_failures.value is not None
    assert unit_of_work.commit_count == 1
