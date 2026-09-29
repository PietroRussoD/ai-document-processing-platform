"""Advisory execution state and timestamp invariants."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from document_platform.domain.processing import (
    AiInvoiceProposalExecution,
    AiInvoiceProposalExecutionStatus,
    InvalidAiInvoiceProposalExecution,
    InvalidAiInvoiceProposalExecutionTransition,
)

RUN_ID = UUID(int=1)
STARTED_AT = datetime(2026, 9, 28, tzinfo=UTC)
FINISHED_AT = STARTED_AT + timedelta(seconds=30)


def running() -> AiInvoiceProposalExecution:
    return AiInvoiceProposalExecution.begin(processing_run_id=RUN_ID, enabled=True, at=STARTED_AT)


def test_records_enabled_execution_without_a_document_status() -> None:
    execution = running()

    assert execution.processing_run_id == RUN_ID
    assert execution.status is AiInvoiceProposalExecutionStatus.RUNNING
    assert execution.started_at == execution.status_changed_at == STARTED_AT
    assert execution.finished_at is None
    assert not hasattr(execution, "document_status")


def test_disabled_execution_never_starts() -> None:
    execution = AiInvoiceProposalExecution.begin(
        processing_run_id=RUN_ID, enabled=False, at=STARTED_AT
    )

    assert execution.status is AiInvoiceProposalExecutionStatus.DISABLED
    assert execution.started_at is None
    assert execution.finished_at == execution.status_changed_at == STARTED_AT


@pytest.mark.parametrize("outcome", ["complete", "fail"])
def test_finishes_without_mutating_running_execution(outcome: str) -> None:
    original = running()

    finished = getattr(original, outcome)(at=FINISHED_AT)

    expected = (
        AiInvoiceProposalExecutionStatus.COMPLETED
        if outcome == "complete"
        else AiInvoiceProposalExecutionStatus.FAILED
    )
    assert finished.status is expected
    assert finished.started_at == STARTED_AT
    assert finished.finished_at == finished.status_changed_at == FINISHED_AT
    assert original.status is AiInvoiceProposalExecutionStatus.RUNNING
    assert original.finished_at is None


@pytest.mark.parametrize("outcome", ["complete", "fail"])
@pytest.mark.parametrize(
    "terminal",
    [
        AiInvoiceProposalExecution.begin(processing_run_id=RUN_ID, enabled=False, at=STARTED_AT),
        running().complete(at=FINISHED_AT),
        running().fail(at=FINISHED_AT),
    ],
)
def test_terminal_execution_cannot_be_changed(
    terminal: AiInvoiceProposalExecution, outcome: str
) -> None:
    with pytest.raises(InvalidAiInvoiceProposalExecutionTransition):
        getattr(terminal, outcome)(at=FINISHED_AT + timedelta(seconds=1))


@pytest.mark.parametrize("outcome", ["complete", "fail"])
@pytest.mark.parametrize(
    "at",
    [STARTED_AT - timedelta(microseconds=1), STARTED_AT.replace(tzinfo=None)],
)
def test_rejects_invalid_transition_time(outcome: str, at: datetime) -> None:
    with pytest.raises(InvalidAiInvoiceProposalExecutionTransition):
        getattr(running(), outcome)(at=at)


def test_allows_instant_completion() -> None:
    assert running().complete(at=STARTED_AT).finished_at == STARTED_AT


@pytest.mark.parametrize(
    "overrides",
    [
        {"processing_run_id": UUID(int=0)},
        {"status": "RUNNING"},
        {"status_changed_at": STARTED_AT.replace(tzinfo=None)},
        {"started_at": STARTED_AT.replace(tzinfo=None)},
        {"started_at": None},
        {"started_at": FINISHED_AT},
        {"status_changed_at": FINISHED_AT},
        {"finished_at": FINISHED_AT},
        {"status": AiInvoiceProposalExecutionStatus.DISABLED},
        {"status": AiInvoiceProposalExecutionStatus.COMPLETED},
        {"status": AiInvoiceProposalExecutionStatus.FAILED},
    ],
)
def test_rejects_invalid_running_record(overrides: dict[str, object]) -> None:
    with pytest.raises(InvalidAiInvoiceProposalExecution):
        replace(running(), **overrides)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "overrides",
    [
        {"finished_at": None},
        {"finished_at": STARTED_AT},
        {"finished_at": FINISHED_AT.replace(tzinfo=None)},
    ],
)
def test_rejects_invalid_terminal_time(overrides: dict[str, object]) -> None:
    with pytest.raises(InvalidAiInvoiceProposalExecution):
        replace(running().complete(at=FINISHED_AT), **overrides)  # type: ignore[arg-type]


def test_execution_is_immutable() -> None:
    execution = running()

    with pytest.raises(FrozenInstanceError):
        execution.status = AiInvoiceProposalExecutionStatus.FAILED  # type: ignore[misc]
