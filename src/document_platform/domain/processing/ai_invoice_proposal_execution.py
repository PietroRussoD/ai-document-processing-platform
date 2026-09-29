"""Advisory AI execution lifecycle, independent of the document outcome."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Self
from uuid import UUID


class AiInvoiceProposalExecutionStatus(StrEnum):
    DISABLED = "DISABLED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class InvalidAiInvoiceProposalExecution(ValueError):
    """Raised when advisory execution metadata violates lifecycle invariants."""


class InvalidAiInvoiceProposalExecutionTransition(ValueError):
    """Raised when an advisory execution cannot enter the requested state."""


@dataclass(frozen=True, slots=True)
class AiInvoiceProposalExecution:
    processing_run_id: UUID
    status: AiInvoiceProposalExecutionStatus
    status_changed_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    def __post_init__(self) -> None:
        if self.processing_run_id.int == 0:
            raise InvalidAiInvoiceProposalExecution("processing_run_id must not be the nil UUID")
        if type(self.status) is not AiInvoiceProposalExecutionStatus:
            raise InvalidAiInvoiceProposalExecution("status must be a known execution status")
        for name, value in (
            ("status_changed_at", self.status_changed_at),
            ("started_at", self.started_at),
            ("finished_at", self.finished_at),
        ):
            if value is not None and not _is_timezone_aware(value):
                raise InvalidAiInvoiceProposalExecution(f"{name} must be timezone-aware")
        if self.status is AiInvoiceProposalExecutionStatus.DISABLED:
            if self.started_at is not None:
                raise InvalidAiInvoiceProposalExecution("a disabled execution must not start")
        elif self.started_at is None:
            raise InvalidAiInvoiceProposalExecution("an enabled execution requires started_at")
        if self.started_at is not None and self.status_changed_at < self.started_at:
            raise InvalidAiInvoiceProposalExecution("status_changed_at must not precede started_at")
        if self.status is AiInvoiceProposalExecutionStatus.RUNNING:
            if self.finished_at is not None:
                raise InvalidAiInvoiceProposalExecution("a running execution must not finish")
            if self.status_changed_at != self.started_at:
                raise InvalidAiInvoiceProposalExecution(
                    "a running execution must retain its start time"
                )
        elif self.finished_at != self.status_changed_at:
            raise InvalidAiInvoiceProposalExecution(
                "finished_at must equal the terminal status time"
            )

    @classmethod
    def begin(cls, *, processing_run_id: UUID, enabled: bool, at: datetime) -> Self:
        return cls(
            processing_run_id=processing_run_id,
            status=(
                AiInvoiceProposalExecutionStatus.RUNNING
                if enabled
                else AiInvoiceProposalExecutionStatus.DISABLED
            ),
            status_changed_at=at,
            started_at=at if enabled else None,
            finished_at=None if enabled else at,
        )

    def complete(self, *, at: datetime) -> Self:
        return self._finish(AiInvoiceProposalExecutionStatus.COMPLETED, at=at)

    def fail(self, *, at: datetime) -> Self:
        return self._finish(AiInvoiceProposalExecutionStatus.FAILED, at=at)

    def _finish(self, target: AiInvoiceProposalExecutionStatus, *, at: datetime) -> Self:
        if self.status is not AiInvoiceProposalExecutionStatus.RUNNING:
            raise InvalidAiInvoiceProposalExecutionTransition(
                f"cannot transition from {self.status} to {target}"
            )
        if not _is_timezone_aware(at):
            raise InvalidAiInvoiceProposalExecutionTransition(
                "transition time must be timezone-aware"
            )
        if at < self.status_changed_at:
            raise InvalidAiInvoiceProposalExecutionTransition(
                "transition time must not move backwards"
            )
        return replace(self, status=target, status_changed_at=at, finished_at=at)


def _is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None
