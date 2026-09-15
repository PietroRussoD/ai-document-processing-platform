"""Workflow-start request domain tests."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from document_platform.domain.processing import (
    InvalidWorkflowStartRequest,
    WorkflowStartRequest,
    WorkflowStartRequestStatus,
)

REQUESTED_AT = datetime(2026, 9, 15, 9, 0, tzinfo=UTC)
RUN_ID = UUID("12121212-1212-4121-8121-121212121212")
CLAIM_TOKEN = UUID("22222222-2222-4222-8222-222222222222")


def test_creates_a_pending_request_with_a_stable_workflow_id() -> None:
    request = WorkflowStartRequest.request(processing_run_id=RUN_ID, requested_at=REQUESTED_AT)

    assert request.processing_run_id == RUN_ID
    assert request.workflow_id == f"process-business-document/{RUN_ID}"
    assert request.status is WorkflowStartRequestStatus.PENDING
    assert request.dispatched_at is None
    assert request.version == 0


def test_claims_and_marks_a_request_as_dispatched() -> None:
    request = WorkflowStartRequest.request(processing_run_id=RUN_ID, requested_at=REQUESTED_AT)
    claimed = request.claim(
        owner="dispatcher-a",
        token=CLAIM_TOKEN,
        at=REQUESTED_AT + timedelta(seconds=1),
        lease_duration=timedelta(seconds=30),
    )

    dispatched = claimed.mark_dispatched(token=CLAIM_TOKEN, at=REQUESTED_AT + timedelta(seconds=2))

    assert claimed.status is WorkflowStartRequestStatus.DISPATCHING
    assert claimed.dispatch_token == CLAIM_TOKEN
    assert claimed.lease_expires_at == REQUESTED_AT + timedelta(seconds=31)
    assert claimed.attempt_count == 1
    assert dispatched.status is WorkflowStartRequestStatus.DISPATCHED
    assert dispatched.dispatched_at == REQUESTED_AT + timedelta(seconds=2)
    assert dispatched.dispatch_token is None
    assert dispatched.version == 2


def test_rejects_dispatching_a_request_twice() -> None:
    request = (
        WorkflowStartRequest.request(
            processing_run_id=RUN_ID,
            requested_at=REQUESTED_AT,
        )
        .claim(
            owner="dispatcher-a",
            token=CLAIM_TOKEN,
            at=REQUESTED_AT + timedelta(seconds=1),
            lease_duration=timedelta(seconds=30),
        )
        .mark_dispatched(token=CLAIM_TOKEN, at=REQUESTED_AT + timedelta(seconds=2))
    )

    with pytest.raises(InvalidWorkflowStartRequest, match="only a claimed request"):
        request.mark_dispatched(token=CLAIM_TOKEN, at=REQUESTED_AT + timedelta(seconds=3))


def test_reclaims_an_expired_claim() -> None:
    request = WorkflowStartRequest.request(
        processing_run_id=RUN_ID,
        requested_at=REQUESTED_AT,
    ).claim(
        owner="dispatcher-a",
        token=CLAIM_TOKEN,
        at=REQUESTED_AT + timedelta(seconds=1),
        lease_duration=timedelta(seconds=30),
    )

    reclaimed = request.claim(
        owner="dispatcher-b",
        token=UUID("33333333-3333-4333-8333-333333333333"),
        at=REQUESTED_AT + timedelta(seconds=31),
        lease_duration=timedelta(seconds=30),
    )

    assert reclaimed.dispatch_owner == "dispatcher-b"
    assert reclaimed.attempt_count == 2
    assert reclaimed.version == 2


def test_rejects_completion_with_a_stale_claim_token() -> None:
    request = WorkflowStartRequest.request(
        processing_run_id=RUN_ID,
        requested_at=REQUESTED_AT,
    ).claim(
        owner="dispatcher-a",
        token=CLAIM_TOKEN,
        at=REQUESTED_AT + timedelta(seconds=1),
        lease_duration=timedelta(seconds=30),
    )

    with pytest.raises(InvalidWorkflowStartRequest, match="does not own"):
        request.mark_dispatched(
            token=UUID("33333333-3333-4333-8333-333333333333"),
            at=REQUESTED_AT + timedelta(seconds=2),
        )
