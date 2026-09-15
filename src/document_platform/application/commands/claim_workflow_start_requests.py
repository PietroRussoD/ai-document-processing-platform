"""Claim durable workflow-start requests for one dispatcher cycle."""

from dataclasses import dataclass
from datetime import timedelta

from document_platform.application.ports import Clock, IdGenerator, UnitOfWorkFactory
from document_platform.domain.processing import WorkflowStartRequest


@dataclass(frozen=True, slots=True)
class ClaimWorkflowStartRequests:
    owner: str
    limit: int
    lease_duration: timedelta


class InvalidWorkflowStartRequestClaim(ValueError):
    """Raised when dispatcher claim inputs are outside the supported bounds."""


class ClaimWorkflowStartRequestsHandler:
    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        clock: Clock,
        id_generator: IdGenerator,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._id_generator = id_generator

    async def __call__(
        self,
        command: ClaimWorkflowStartRequests,
    ) -> tuple[WorkflowStartRequest, ...]:
        _validate(command)
        claimed_at = self._clock()
        async with self._unit_of_work_factory() as unit_of_work:
            requests = await unit_of_work.workflow_start_requests.claim_pending(
                owner=command.owner,
                claimed_at=claimed_at,
                lease_duration=command.lease_duration,
                limit=command.limit,
                token_generator=self._id_generator,
            )
            if requests:
                await unit_of_work.commit()
            return requests


def _validate(command: ClaimWorkflowStartRequests) -> None:
    if command.owner != command.owner.strip() or not command.owner:
        raise InvalidWorkflowStartRequestClaim("owner must be non-empty and trimmed")
    if len(command.owner) > 64:
        raise InvalidWorkflowStartRequestClaim("owner must be at most 64 characters")
    if not 1 <= command.limit <= 100:
        raise InvalidWorkflowStartRequestClaim("limit must be between 1 and 100")
    if command.lease_duration <= timedelta(0):
        raise InvalidWorkflowStartRequestClaim("lease_duration must be positive")
