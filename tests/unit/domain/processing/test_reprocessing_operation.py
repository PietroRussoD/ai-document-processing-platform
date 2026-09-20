"""Reprocessing-operation domain tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from document_platform.domain.processing import (
    ConflictingReprocessingIdempotencyKey,
    InvalidReprocessingOperation,
    ReprocessingOperation,
)

OPERATION_ID = UUID("1a1a1a1a-1111-4111-8111-111111111111")
DOCUMENT_ID = UUID("2b2b2b2b-2222-4222-8222-222222222222")
SOURCE_RUN_ID = UUID("3c3c3c3c-3333-4333-8333-333333333333")
REPLACEMENT_RUN_ID = UUID("4d4d4d4d-4444-4444-8444-444444444444")
REQUESTED_AT = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)


def requested_operation(**overrides: object) -> ReprocessingOperation:
    values: dict[str, object] = {
        "operation_id": OPERATION_ID,
        "document_id": DOCUMENT_ID,
        "source_run_id": SOURCE_RUN_ID,
        "replacement_run_id": REPLACEMENT_RUN_ID,
        "requested_by": "local-review-operator",
        "reason": "Retry after the upstream outage was resolved.",
        "idempotency_key": "reprocess-20260920-001",
        "requested_at": REQUESTED_AT,
    }
    values.update(overrides)
    return ReprocessingOperation.request(**values)  # type: ignore[arg-type]


def test_creates_an_immutable_reprocessing_audit_record() -> None:
    operation = requested_operation()

    assert operation.id == OPERATION_ID
    assert operation.document_id == DOCUMENT_ID
    assert operation.source_run_id == SOURCE_RUN_ID
    assert operation.replacement_run_id == REPLACEMENT_RUN_ID
    assert operation.request_fingerprint


def test_accepts_an_equivalent_idempotent_replay() -> None:
    operation = requested_operation()

    operation.ensure_replay_matches(
        source_run_id=SOURCE_RUN_ID,
        reason="Retry after the upstream outage was resolved.",
    )


@pytest.mark.parametrize(
    ("source_run_id", "reason"),
    [
        (
            UUID("5e5e5e5e-5555-4555-8555-555555555555"),
            "Retry after the upstream outage was resolved.",
        ),
        (SOURCE_RUN_ID, "Retry after another upstream outage."),
    ],
)
def test_rejects_a_conflicting_idempotent_replay(source_run_id: UUID, reason: str) -> None:
    operation = requested_operation()

    with pytest.raises(ConflictingReprocessingIdempotencyKey):
        operation.ensure_replay_matches(source_run_id=source_run_id, reason=reason)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("operation_id", UUID(int=0)),
        ("document_id", UUID(int=0)),
        ("source_run_id", UUID(int=0)),
        ("replacement_run_id", UUID(int=0)),
        ("replacement_run_id", SOURCE_RUN_ID),
        ("requested_by", " "),
        ("reason", " "),
        ("idempotency_key", " "),
        ("requested_at", datetime(2026, 9, 20, 9, 0)),
    ],
)
def test_rejects_invalid_reprocessing_operation_data(field: str, invalid_value: object) -> None:
    with pytest.raises(InvalidReprocessingOperation):
        requested_operation(**{field: invalid_value})
