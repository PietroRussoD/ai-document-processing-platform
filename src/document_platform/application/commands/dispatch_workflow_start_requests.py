"""Start claimed workflows outside the database transaction that claimed them."""

from dataclasses import dataclass

from document_platform.application.commands.claim_workflow_start_requests import (
    ClaimWorkflowStartRequests,
    ClaimWorkflowStartRequestsHandler,
)
from document_platform.application.ports import (
    Clock,
    ConcurrentWorkflowStartRequestUpdate,
    UnitOfWorkFactory,
    WorkflowStarter,
)
from document_platform.domain.processing import WorkflowStartRequest


@dataclass(frozen=True, slots=True)
class WorkflowStartDispatchResult:
    claimed_count: int
    dispatched_count: int
    deferred_count: int


class DispatchWorkflowStartRequestsHandler:
    def __init__(
        self,
        *,
        claim_workflow_start_requests: ClaimWorkflowStartRequestsHandler,
        workflow_starter: WorkflowStarter,
        unit_of_work_factory: UnitOfWorkFactory,
        clock: Clock,
    ) -> None:
        self._claim_workflow_start_requests = claim_workflow_start_requests
        self._workflow_starter = workflow_starter
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def __call__(
        self,
        command: ClaimWorkflowStartRequests,
    ) -> WorkflowStartDispatchResult:
        claimed = await self._claim_workflow_start_requests(command)
        dispatched_count = 0
        deferred_count = 0

        for request in claimed:
            try:
                await self._workflow_starter.start(
                    workflow_id=request.workflow_id,
                    processing_run_id=request.processing_run_id,
                )
                await self._mark_dispatched(request)
            except ConcurrentWorkflowStartRequestUpdate:
                deferred_count += 1
            except Exception:
                deferred_count += 1
            else:
                dispatched_count += 1

        return WorkflowStartDispatchResult(
            claimed_count=len(claimed),
            dispatched_count=dispatched_count,
            deferred_count=deferred_count,
        )

    async def _mark_dispatched(self, request: WorkflowStartRequest) -> None:
        token = request.dispatch_token
        if token is None:
            raise RuntimeError("a claimed workflow start request must have a dispatch token")

        dispatched = request.mark_dispatched(token=token, at=self._clock())
        async with self._unit_of_work_factory() as unit_of_work:
            await unit_of_work.workflow_start_requests.update(dispatched)
            await unit_of_work.commit()
