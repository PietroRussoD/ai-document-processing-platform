"""Durable handoff request for starting a processing workflow."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class WorkflowStartRequestStatus(StrEnum):
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"


class InvalidWorkflowStartRequest(ValueError):
    """Raised when a workflow-start request violates a domain invariant."""


@dataclass(frozen=True, slots=True)
class WorkflowStartRequest:
    processing_run_id: UUID
    workflow_id: str
    status: WorkflowStartRequestStatus
    requested_at: datetime
    dispatched_at: datetime | None
    version: int

    def __post_init__(self) -> None:
        if self.processing_run_id.int == 0:
            raise InvalidWorkflowStartRequest("processing_run_id must not be the nil UUID")
        if self.workflow_id != self.workflow_id.strip() or not self.workflow_id:
            raise InvalidWorkflowStartRequest("workflow_id must be non-empty and trimmed")
        if len(self.workflow_id) > 128:
            raise InvalidWorkflowStartRequest("workflow_id must be at most 128 characters")
        if not _is_timezone_aware(self.requested_at):
            raise InvalidWorkflowStartRequest("requested_at must be timezone-aware")
        if self.dispatched_at is not None:
            if not _is_timezone_aware(self.dispatched_at):
                raise InvalidWorkflowStartRequest("dispatched_at must be timezone-aware")
            if self.dispatched_at < self.requested_at:
                raise InvalidWorkflowStartRequest("dispatched_at must not precede requested_at")
        if (self.status is WorkflowStartRequestStatus.DISPATCHED) != (
            self.dispatched_at is not None
        ):
            raise InvalidWorkflowStartRequest("dispatch status must match dispatched_at")
        if self.version < 0:
            raise InvalidWorkflowStartRequest("version must not be negative")

    @classmethod
    def request(cls, *, processing_run_id: UUID, requested_at: datetime) -> "WorkflowStartRequest":
        return cls(
            processing_run_id=processing_run_id,
            workflow_id=f"process-business-document/{processing_run_id}",
            status=WorkflowStartRequestStatus.PENDING,
            requested_at=requested_at,
            dispatched_at=None,
            version=0,
        )

    def mark_dispatched(self, *, at: datetime) -> "WorkflowStartRequest":
        if self.status is not WorkflowStartRequestStatus.PENDING:
            raise InvalidWorkflowStartRequest("only a pending request can be dispatched")
        if not _is_timezone_aware(at):
            raise InvalidWorkflowStartRequest("dispatch time must be timezone-aware")
        if at < self.requested_at:
            raise InvalidWorkflowStartRequest("dispatch time must not precede requested_at")
        return replace(
            self,
            status=WorkflowStartRequestStatus.DISPATCHED,
            dispatched_at=at,
            version=self.version + 1,
        )


def _is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None
