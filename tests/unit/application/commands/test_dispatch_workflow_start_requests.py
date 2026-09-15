"""Workflow-start dispatch application tests."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from document_platform.application.commands import (
    ClaimWorkflowStartRequests,
    ClaimWorkflowStartRequestsHandler,
    DispatchWorkflowStartRequestsHandler,
    WorkflowStartDispatchResult,
)
from document_platform.application.ports import UnitOfWork, WorkflowStarter
from document_platform.domain.processing import WorkflowStartRequest

CLAIMED_AT = datetime(2026, 9, 15, 11, 0, tzinfo=UTC)
RUN_ID = UUID("34343434-3434-4434-8434-343434343434")
TOKEN = UUID("35353535-3535-4535-8535-353535353535")


class RecordingWorkflowStartRequestRepository:
    def __init__(self, request: WorkflowStartRequest) -> None:
        self.request = request
        self.updated: list[WorkflowStartRequest] = []

    async def claim_pending(
        self,
        *,
        owner: str,
        claimed_at: datetime,
        lease_duration: timedelta,
        limit: int,
        token_generator: Callable[[], UUID],
    ) -> tuple[WorkflowStartRequest, ...]:
        return (self.request,)

    async def update(self, request: WorkflowStartRequest) -> None:
        self.updated.append(request)


class RecordingUnitOfWork:
    def __init__(self, request: WorkflowStartRequest) -> None:
        self.workflow_start_requests = RecordingWorkflowStartRequestRepository(request)
        self.commit_count = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.commit_count += 1


class RecordingWorkflowStarter:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, UUID]] = []

    async def start(self, *, workflow_id: str, processing_run_id: UUID) -> None:
        self.calls.append((workflow_id, processing_run_id))
        if self.error is not None:
            raise self.error


def handler(
    unit_of_work: RecordingUnitOfWork,
    workflow_starter: RecordingWorkflowStarter,
) -> DispatchWorkflowStartRequestsHandler:
    claim = ClaimWorkflowStartRequestsHandler(
        unit_of_work_factory=lambda: cast(UnitOfWork, unit_of_work),
        clock=lambda: CLAIMED_AT,
        id_generator=lambda: TOKEN,
    )
    return DispatchWorkflowStartRequestsHandler(
        claim_workflow_start_requests=claim,
        workflow_starter=cast(WorkflowStarter, workflow_starter),
        unit_of_work_factory=lambda: cast(UnitOfWork, unit_of_work),
        clock=lambda: CLAIMED_AT + timedelta(seconds=1),
    )


def claimed_request() -> WorkflowStartRequest:
    return WorkflowStartRequest.request(
        processing_run_id=RUN_ID,
        requested_at=CLAIMED_AT,
    ).claim(
        owner="dispatcher-a",
        token=TOKEN,
        at=CLAIMED_AT,
        lease_duration=timedelta(seconds=30),
    )


@pytest.mark.anyio
async def test_starts_a_claimed_workflow_then_marks_its_request_dispatched() -> None:
    request = claimed_request()
    unit_of_work = RecordingUnitOfWork(request)
    workflow_starter = RecordingWorkflowStarter()

    result = await handler(unit_of_work, workflow_starter)(
        ClaimWorkflowStartRequests("dispatcher-a", 10, timedelta(seconds=30))
    )

    assert result == WorkflowStartDispatchResult(1, 1, 0)
    assert workflow_starter.calls == [(request.workflow_id, RUN_ID)]
    assert unit_of_work.workflow_start_requests.updated[0].dispatched_at == CLAIMED_AT + timedelta(
        seconds=1
    )
    assert unit_of_work.commit_count == 2


@pytest.mark.anyio
async def test_leaves_a_claimed_request_for_recovery_when_workflow_start_fails() -> None:
    request = claimed_request()
    unit_of_work = RecordingUnitOfWork(request)
    workflow_starter = RecordingWorkflowStarter(RuntimeError("Temporal unavailable"))

    result = await handler(unit_of_work, workflow_starter)(
        ClaimWorkflowStartRequests("dispatcher-a", 10, timedelta(seconds=30))
    )

    assert result == WorkflowStartDispatchResult(1, 0, 1)
    assert unit_of_work.workflow_start_requests.updated == []
    assert unit_of_work.commit_count == 1
