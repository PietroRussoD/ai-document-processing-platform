"""Temporal workflow-start adapter tests."""

from typing import Any, cast
from uuid import UUID

import pytest
from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from document_platform.adapters.outbound.temporal import TemporalWorkflowStarter
from document_platform.adapters.outbound.temporal.temporal_workflow_starter import (
    PROCESS_BUSINESS_DOCUMENT_WORKFLOW,
)

RUN_ID = UUID("31313131-3131-4131-8131-313131313131")
WORKFLOW_ID = f"process-business-document/{RUN_ID}"


class RecordingTemporalClient:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    async def start_workflow(self, *args: Any, **kwargs: Any) -> None:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error


def starter(client: RecordingTemporalClient) -> TemporalWorkflowStarter:
    return TemporalWorkflowStarter(cast(Client, client), task_queue="document-processing")


@pytest.mark.anyio
async def test_starts_the_stable_processing_workflow_idempotently() -> None:
    client = RecordingTemporalClient()

    await starter(client).start(workflow_id=WORKFLOW_ID, processing_run_id=RUN_ID)

    assert client.calls == [
        (
            (PROCESS_BUSINESS_DOCUMENT_WORKFLOW, str(RUN_ID)),
            {
                "id": WORKFLOW_ID,
                "task_queue": "document-processing",
                "id_reuse_policy": WorkflowIDReusePolicy.REJECT_DUPLICATE,
                "id_conflict_policy": WorkflowIDConflictPolicy.USE_EXISTING,
            },
        )
    ]


@pytest.mark.anyio
async def test_treats_an_existing_workflow_as_an_idempotent_start() -> None:
    client = RecordingTemporalClient(
        WorkflowAlreadyStartedError(WORKFLOW_ID, PROCESS_BUSINESS_DOCUMENT_WORKFLOW)
    )

    await starter(client).start(workflow_id=WORKFLOW_ID, processing_run_id=RUN_ID)

    assert len(client.calls) == 1


def test_rejects_an_empty_task_queue() -> None:
    with pytest.raises(ValueError, match="task_queue"):
        TemporalWorkflowStarter(cast(Client, RecordingTemporalClient()), task_queue=" ")
