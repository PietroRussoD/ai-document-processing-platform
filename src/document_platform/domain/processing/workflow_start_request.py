"""Durable handoff request for starting a processing workflow."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID


class WorkflowStartRequestStatus(StrEnum):
    PENDING = "PENDING"
    DISPATCHING = "DISPATCHING"
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
    dispatch_owner: str | None
    dispatch_token: UUID | None
    lease_expires_at: datetime | None
    attempt_count: int
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
        has_claim = (
            self.dispatch_owner is not None
            and self.dispatch_token is not None
            and self.lease_expires_at is not None
        )
        if (self.status is WorkflowStartRequestStatus.DISPATCHING) != has_claim:
            raise InvalidWorkflowStartRequest("dispatching status must match an active claim")
        if self.status is not WorkflowStartRequestStatus.DISPATCHING and any(
            value is not None
            for value in (self.dispatch_owner, self.dispatch_token, self.lease_expires_at)
        ):
            raise InvalidWorkflowStartRequest("only a dispatching request may have an active claim")
        if self.dispatch_owner is not None:
            if self.dispatch_owner != self.dispatch_owner.strip() or not self.dispatch_owner:
                raise InvalidWorkflowStartRequest("dispatch_owner must be non-empty and trimmed")
            if len(self.dispatch_owner) > 64:
                raise InvalidWorkflowStartRequest("dispatch_owner must be at most 64 characters")
        if self.lease_expires_at is not None:
            if not _is_timezone_aware(self.lease_expires_at):
                raise InvalidWorkflowStartRequest("lease_expires_at must be timezone-aware")
            if self.lease_expires_at <= self.requested_at:
                raise InvalidWorkflowStartRequest("lease_expires_at must follow requested_at")
        if self.attempt_count < 0:
            raise InvalidWorkflowStartRequest("attempt_count must not be negative")
        if self.status is WorkflowStartRequestStatus.PENDING and self.attempt_count != 0:
            raise InvalidWorkflowStartRequest("a pending request must have zero attempts")
        if self.status is not WorkflowStartRequestStatus.PENDING and self.attempt_count < 1:
            raise InvalidWorkflowStartRequest("a claimed request must have at least one attempt")
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
            dispatch_owner=None,
            dispatch_token=None,
            lease_expires_at=None,
            attempt_count=0,
            version=0,
        )

    def can_be_claimed(self, *, at: datetime) -> bool:
        if not _is_timezone_aware(at):
            raise InvalidWorkflowStartRequest("claim time must be timezone-aware")
        return self.status is WorkflowStartRequestStatus.PENDING or (
            self.status is WorkflowStartRequestStatus.DISPATCHING
            and self.lease_expires_at is not None
            and self.lease_expires_at <= at
        )

    def claim(
        self,
        *,
        owner: str,
        token: UUID,
        at: datetime,
        lease_duration: timedelta,
    ) -> "WorkflowStartRequest":
        if not self.can_be_claimed(at=at):
            raise InvalidWorkflowStartRequest("request is not claimable")
        if owner != owner.strip() or not owner:
            raise InvalidWorkflowStartRequest("claim owner must be non-empty and trimmed")
        if len(owner) > 64:
            raise InvalidWorkflowStartRequest("claim owner must be at most 64 characters")
        if token.int == 0:
            raise InvalidWorkflowStartRequest("claim token must not be the nil UUID")
        if lease_duration <= timedelta(0):
            raise InvalidWorkflowStartRequest("lease duration must be positive")
        if at < self.requested_at:
            raise InvalidWorkflowStartRequest("claim time must not precede requested_at")
        return replace(
            self,
            status=WorkflowStartRequestStatus.DISPATCHING,
            dispatch_owner=owner,
            dispatch_token=token,
            lease_expires_at=at + lease_duration,
            attempt_count=self.attempt_count + 1,
            version=self.version + 1,
        )

    def mark_dispatched(self, *, token: UUID, at: datetime) -> "WorkflowStartRequest":
        if self.status is not WorkflowStartRequestStatus.DISPATCHING:
            raise InvalidWorkflowStartRequest("only a claimed request can be dispatched")
        if token != self.dispatch_token:
            raise InvalidWorkflowStartRequest("dispatch token does not own the active claim")
        if not _is_timezone_aware(at):
            raise InvalidWorkflowStartRequest("dispatch time must be timezone-aware")
        if at < self.requested_at:
            raise InvalidWorkflowStartRequest("dispatch time must not precede requested_at")
        return replace(
            self,
            status=WorkflowStartRequestStatus.DISPATCHED,
            dispatched_at=at,
            dispatch_owner=None,
            dispatch_token=None,
            lease_expires_at=None,
            version=self.version + 1,
        )


def _is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None
