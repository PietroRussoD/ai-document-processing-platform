"""Processing-run aggregate and lifecycle rules."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID


class ProcessingRunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_RETRY = "WAITING_RETRY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class InvalidProcessingRun(ValueError):
    """Raised when processing-run data violates a domain invariant."""


class InvalidProcessingRunTransition(ValueError):
    """Raised when a processing-run lifecycle transition is not allowed."""


_TERMINAL_STATUSES = frozenset(
    {
        ProcessingRunStatus.COMPLETED,
        ProcessingRunStatus.FAILED,
        ProcessingRunStatus.CANCELLED,
    }
)
_STARTED_STATUSES = frozenset(
    {
        ProcessingRunStatus.RUNNING,
        ProcessingRunStatus.WAITING_RETRY,
        ProcessingRunStatus.REVIEW_REQUIRED,
        ProcessingRunStatus.COMPLETED,
        ProcessingRunStatus.FAILED,
    }
)
_ALLOWED_TRANSITIONS: dict[ProcessingRunStatus, frozenset[ProcessingRunStatus]] = {
    ProcessingRunStatus.QUEUED: frozenset(
        {ProcessingRunStatus.RUNNING, ProcessingRunStatus.CANCELLED}
    ),
    ProcessingRunStatus.RUNNING: frozenset(
        {
            ProcessingRunStatus.WAITING_RETRY,
            ProcessingRunStatus.REVIEW_REQUIRED,
            ProcessingRunStatus.COMPLETED,
            ProcessingRunStatus.FAILED,
            ProcessingRunStatus.CANCELLED,
        }
    ),
    ProcessingRunStatus.WAITING_RETRY: frozenset(
        {ProcessingRunStatus.RUNNING, ProcessingRunStatus.CANCELLED}
    ),
    ProcessingRunStatus.REVIEW_REQUIRED: frozenset(
        {ProcessingRunStatus.RUNNING, ProcessingRunStatus.COMPLETED}
    ),
    ProcessingRunStatus.COMPLETED: frozenset(),
    ProcessingRunStatus.FAILED: frozenset(),
    ProcessingRunStatus.CANCELLED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class ProcessingRun:
    id: UUID
    document_id: UUID
    status: ProcessingRunStatus
    queued_at: datetime
    started_at: datetime | None
    status_changed_at: datetime
    finished_at: datetime | None
    attempt_count: int
    version: int

    def __post_init__(self) -> None:
        if self.id.int == 0:
            raise InvalidProcessingRun("id must not be the nil UUID")
        if self.document_id.int == 0:
            raise InvalidProcessingRun("document_id must not be the nil UUID")
        if not _is_timezone_aware(self.queued_at):
            raise InvalidProcessingRun("queued_at must be timezone-aware")
        if not _is_timezone_aware(self.status_changed_at):
            raise InvalidProcessingRun("status_changed_at must be timezone-aware")
        if self.status_changed_at < self.queued_at:
            raise InvalidProcessingRun("status_changed_at must not precede queued_at")
        if self.started_at is not None:
            if not _is_timezone_aware(self.started_at):
                raise InvalidProcessingRun("started_at must be timezone-aware")
            if self.started_at < self.queued_at:
                raise InvalidProcessingRun("started_at must not precede queued_at")
            if self.status_changed_at < self.started_at:
                raise InvalidProcessingRun("status_changed_at must not precede started_at")
        if self.finished_at is not None:
            if not _is_timezone_aware(self.finished_at):
                raise InvalidProcessingRun("finished_at must be timezone-aware")
            if self.finished_at < (self.started_at or self.queued_at):
                raise InvalidProcessingRun("finished_at must not precede the run")
            if self.finished_at != self.status_changed_at:
                raise InvalidProcessingRun("finished_at must equal the final status change time")
        if self.status is ProcessingRunStatus.QUEUED and self.started_at is not None:
            raise InvalidProcessingRun("a queued run must not have started")
        if self.status in _STARTED_STATUSES and self.started_at is None:
            raise InvalidProcessingRun(f"{self.status} requires started_at")
        if (self.status in _TERMINAL_STATUSES) != (self.finished_at is not None):
            raise InvalidProcessingRun("finished_at must exist only for a terminal status")
        if self.started_at is None and self.attempt_count != 0:
            raise InvalidProcessingRun("an unstarted run must have zero attempts")
        if self.started_at is not None and self.attempt_count < 1:
            raise InvalidProcessingRun("a started run must have at least one attempt")
        if self.version < 0:
            raise InvalidProcessingRun("version must not be negative")

    @classmethod
    def queue(
        cls,
        *,
        run_id: UUID,
        document_id: UUID,
        queued_at: datetime,
    ) -> Self:
        return cls(
            id=run_id,
            document_id=document_id,
            status=ProcessingRunStatus.QUEUED,
            queued_at=queued_at,
            started_at=None,
            status_changed_at=queued_at,
            finished_at=None,
            attempt_count=0,
            version=0,
        )

    def start(self, *, at: datetime) -> Self:
        self._require_status(ProcessingRunStatus.QUEUED, operation="start")
        return self._transition_to(
            ProcessingRunStatus.RUNNING,
            at=at,
            mark_started=True,
            increment_attempt=True,
        )

    def wait_for_retry(self, *, at: datetime) -> Self:
        return self._transition_to(ProcessingRunStatus.WAITING_RETRY, at=at)

    def retry(self, *, at: datetime) -> Self:
        self._require_status(ProcessingRunStatus.WAITING_RETRY, operation="retry")
        return self._transition_to(
            ProcessingRunStatus.RUNNING,
            at=at,
            increment_attempt=True,
        )

    def require_review(self, *, at: datetime) -> Self:
        return self._transition_to(ProcessingRunStatus.REVIEW_REQUIRED, at=at)

    def resume_after_review(self, *, at: datetime) -> Self:
        self._require_status(ProcessingRunStatus.REVIEW_REQUIRED, operation="resume review")
        return self._transition_to(ProcessingRunStatus.RUNNING, at=at)

    def complete_after_review(self, *, at: datetime) -> Self:
        self._require_status(ProcessingRunStatus.REVIEW_REQUIRED, operation="complete review")
        return self._transition_to(ProcessingRunStatus.COMPLETED, at=at, mark_finished=True)

    def complete(self, *, at: datetime) -> Self:
        return self._transition_to(ProcessingRunStatus.COMPLETED, at=at, mark_finished=True)

    def fail(self, *, at: datetime) -> Self:
        return self._transition_to(ProcessingRunStatus.FAILED, at=at, mark_finished=True)

    def cancel(self, *, at: datetime) -> Self:
        return self._transition_to(ProcessingRunStatus.CANCELLED, at=at, mark_finished=True)

    def _require_status(self, expected: ProcessingRunStatus, *, operation: str) -> None:
        if self.status is not expected:
            raise InvalidProcessingRunTransition(f"cannot {operation} from {self.status}")

    def _transition_to(
        self,
        target: ProcessingRunStatus,
        *,
        at: datetime,
        mark_started: bool = False,
        increment_attempt: bool = False,
        mark_finished: bool = False,
    ) -> Self:
        if target not in _ALLOWED_TRANSITIONS[self.status]:
            raise InvalidProcessingRunTransition(
                f"cannot transition from {self.status} to {target}"
            )
        if not _is_timezone_aware(at):
            raise InvalidProcessingRunTransition("transition time must be timezone-aware")
        if at < self.status_changed_at:
            raise InvalidProcessingRunTransition("transition time must not move backwards")

        return replace(
            self,
            status=target,
            started_at=at if mark_started else self.started_at,
            status_changed_at=at,
            finished_at=at if mark_finished else self.finished_at,
            attempt_count=self.attempt_count + int(increment_attempt),
            version=self.version + 1,
        )


def _is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None
