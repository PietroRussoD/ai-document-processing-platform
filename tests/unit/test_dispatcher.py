"""Standalone dispatcher process tests."""

from datetime import timedelta

import pytest

from document_platform.application.commands import (
    ClaimWorkflowStartRequests,
    WorkflowStartDispatchResult,
)
from document_platform.dispatcher import run_dispatch_cycle
from document_platform.settings import Settings


@pytest.mark.anyio
async def test_runs_a_cycle_with_typed_dispatcher_settings() -> None:
    commands: list[ClaimWorkflowStartRequests] = []

    async def dispatch(command: ClaimWorkflowStartRequests) -> WorkflowStartDispatchResult:
        commands.append(command)
        return WorkflowStartDispatchResult(0, 0, 0)

    result = await run_dispatch_cycle(
        dispatch,
        Settings(
            dispatcher_owner="worker-a",
            dispatcher_batch_size=7,
            dispatcher_lease_seconds=45,
        ),
    )

    assert result == WorkflowStartDispatchResult(0, 0, 0)
    assert commands == [
        ClaimWorkflowStartRequests(
            owner="worker-a",
            limit=7,
            lease_duration=timedelta(seconds=45),
        )
    ]
