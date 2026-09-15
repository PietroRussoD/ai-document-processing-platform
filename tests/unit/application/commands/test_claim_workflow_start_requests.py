"""Workflow-start request claim application tests."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from document_platform.application.commands import (
    ClaimWorkflowStartRequests,
    ClaimWorkflowStartRequestsHandler,
    InvalidWorkflowStartRequestClaim,
)
from document_platform.application.ports import UnitOfWork
from document_platform.domain.processing import WorkflowStartRequest

CLAIMED_AT = datetime(2026, 9, 15, 10, 0, tzinfo=UTC)
RUN_ID = UUID("24242424-2424-4242-8242-242424242424")
TOKEN = UUID("25252525-2525-4252-8252-252525252525")


class RecordingWorkflowStartRequestRepository:
    def __init__(self, result: tuple[WorkflowStartRequest, ...]) -> None:
        self.result = result
        self.claims: list[tuple[str, datetime, timedelta, int, Callable[[], UUID]]] = []

    async def claim_pending(
        self,
        *,
        owner: str,
        claimed_at: datetime,
        lease_duration: timedelta,
        limit: int,
        token_generator: Callable[[], UUID],
    ) -> tuple[WorkflowStartRequest, ...]:
        self.claims.append((owner, claimed_at, lease_duration, limit, token_generator))
        return self.result


class RecordingUnitOfWork:
    def __init__(self, result: tuple[WorkflowStartRequest, ...]) -> None:
        self.workflow_start_requests = RecordingWorkflowStartRequestRepository(result)
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


def handler(unit_of_work: RecordingUnitOfWork) -> ClaimWorkflowStartRequestsHandler:
    return ClaimWorkflowStartRequestsHandler(
        unit_of_work_factory=lambda: cast(UnitOfWork, unit_of_work),
        clock=lambda: CLAIMED_AT,
        id_generator=lambda: TOKEN,
    )


@pytest.mark.anyio
async def test_claims_a_bounded_batch_and_commits_it() -> None:
    claimed = WorkflowStartRequest.request(
        processing_run_id=RUN_ID,
        requested_at=CLAIMED_AT,
    ).claim(
        owner="dispatcher-a",
        token=TOKEN,
        at=CLAIMED_AT,
        lease_duration=timedelta(seconds=30),
    )
    unit_of_work = RecordingUnitOfWork((claimed,))

    result = await handler(unit_of_work)(
        ClaimWorkflowStartRequests(
            owner="dispatcher-a",
            limit=10,
            lease_duration=timedelta(seconds=30),
        )
    )

    assert result == (claimed,)
    assert unit_of_work.commit_count == 1
    assert unit_of_work.workflow_start_requests.claims[0][:4] == (
        "dispatcher-a",
        CLAIMED_AT,
        timedelta(seconds=30),
        10,
    )


@pytest.mark.anyio
async def test_does_not_open_a_unit_of_work_for_an_invalid_claim() -> None:
    unit_of_work = RecordingUnitOfWork(())
    factory_called = False

    def factory() -> UnitOfWork:
        nonlocal factory_called
        factory_called = True
        return cast(UnitOfWork, unit_of_work)

    claim = ClaimWorkflowStartRequestsHandler(
        unit_of_work_factory=factory,
        clock=lambda: CLAIMED_AT,
        id_generator=lambda: TOKEN,
    )

    with pytest.raises(InvalidWorkflowStartRequestClaim, match="limit"):
        await claim(
            ClaimWorkflowStartRequests(
                owner="dispatcher-a",
                limit=0,
                lease_duration=timedelta(seconds=30),
            )
        )

    assert factory_called is False
