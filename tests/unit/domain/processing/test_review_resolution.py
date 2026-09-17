"""Manual review-resolution domain tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from document_platform.domain.processing import (
    InvalidReviewResolution,
    ReviewResolution,
    ReviewResolutionDecision,
)
from document_platform.domain.processing.review_resolution import (
    MAX_REVIEW_NOTE_LENGTH,
    MAX_REVIEWER_ID_LENGTH,
)

RUN_ID = UUID("b8b8b8b8-b8b8-48b8-88b8-b8b8b8b8b8b8")
AT = datetime(2026, 9, 17, 14, 0, tzinfo=UTC)


def resolution(**overrides: object) -> ReviewResolution:
    values: dict[str, object] = {
        "processing_run_id": RUN_ID,
        "decision": ReviewResolutionDecision.APPROVE,
        "reviewer_id": "operator-42",
        "review_note": None,
        "resolved_at": AT,
    }
    values.update(overrides)
    return ReviewResolution(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("processing_run_id", UUID(int=0)),
        ("reviewer_id", "   "),
        ("reviewer_id", "a" * (MAX_REVIEWER_ID_LENGTH + 1)),
        ("review_note", "   "),
        ("review_note", "a" * (MAX_REVIEW_NOTE_LENGTH + 1)),
        ("resolved_at", datetime(2026, 9, 17, 14, 0)),
    ],
)
def test_rejects_invalid_review_resolution_data(field: str, value: object) -> None:
    with pytest.raises(InvalidReviewResolution):
        resolution(**{field: value})


def test_accepts_a_bounded_optional_note() -> None:
    result = resolution(review_note="Reviewed by an authenticated operator later.")

    assert result.decision is ReviewResolutionDecision.APPROVE
