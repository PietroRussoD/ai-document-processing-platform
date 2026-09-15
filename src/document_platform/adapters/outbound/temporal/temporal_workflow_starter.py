"""Temporal implementation of the durable workflow-start boundary."""

from uuid import UUID

from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from document_platform.application.ports.workflow_starter import PROCESS_BUSINESS_DOCUMENT_WORKFLOW


class TemporalWorkflowStarter:
    def __init__(self, client: Client, *, task_queue: str) -> None:
        if task_queue != task_queue.strip() or not task_queue:
            raise ValueError("task_queue must be non-empty and trimmed")
        self._client = client
        self._task_queue = task_queue

    async def start(
        self,
        *,
        workflow_id: str,
        processing_run_id: UUID,
    ) -> None:
        try:
            await self._client.start_workflow(
                PROCESS_BUSINESS_DOCUMENT_WORKFLOW,
                str(processing_run_id),
                id=workflow_id,
                task_queue=self._task_queue,
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
            )
        except WorkflowAlreadyStartedError:
            # A prior attempt reached Temporal before losing its database lease.
            return
