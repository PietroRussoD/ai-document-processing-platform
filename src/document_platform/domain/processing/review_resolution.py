"""Immutable manual resolution of a processing-review handoff."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

MAX_REVIEW_NOTE_LENGTH = 2_000


class ReviewResolutionDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class InvalidReviewResolution(ValueError):
    """Raised when a manual review resolution violates its invariants."""


@dataclass(frozen=True, slots=True)
class ReviewResolution:
    processing_run_id: UUID
    decision: ReviewResolutionDecision
    review_note: str | None
    resolved_at: datetime

    def __post_init__(self) -> None:
        if self.processing_run_id.int == 0:
            raise InvalidReviewResolution("processing_run_id must not be the nil UUID")
        if self.review_note is not None:
            if not self.review_note.strip():
                raise InvalidReviewResolution("review_note must not be blank when provided")
            if len(self.review_note) > MAX_REVIEW_NOTE_LENGTH:
                raise InvalidReviewResolution(
                    f"review_note must not exceed {MAX_REVIEW_NOTE_LENGTH} characters"
                )
        if self.resolved_at.tzinfo is None or self.resolved_at.utcoffset() is None:
            raise InvalidReviewResolution("resolved_at must be timezone-aware")
