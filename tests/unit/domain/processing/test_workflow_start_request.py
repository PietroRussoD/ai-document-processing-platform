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


def test_creates_a_pending_request_with_a_stable_workflow_id() -> None:
    request = WorkflowStartRequest.request(processing_run_id=RUN_ID, requested_at=REQUESTED_AT)

    assert request.processing_run_id == RUN_ID
    assert request.workflow_id == f"process-business-document/{RUN_ID}"
    assert request.status is WorkflowStartRequestStatus.PENDING
    assert request.dispatched_at is None
    assert request.version == 0


def test_marks_a_pending_request_as_dispatched() -> None:
    request = WorkflowStartRequest.request(processing_run_id=RUN_ID, requested_at=REQUESTED_AT)

    dispatched = request.mark_dispatched(at=REQUESTED_AT + timedelta(seconds=1))

    assert dispatched.status is WorkflowStartRequestStatus.DISPATCHED
    assert dispatched.dispatched_at == REQUESTED_AT + timedelta(seconds=1)
    assert dispatched.version == 1


def test_rejects_dispatching_a_request_twice() -> None:
    request = WorkflowStartRequest.request(
        processing_run_id=RUN_ID,
        requested_at=REQUESTED_AT,
    ).mark_dispatched(at=REQUESTED_AT + timedelta(seconds=1))

    with pytest.raises(InvalidWorkflowStartRequest, match="only a pending request"):
        request.mark_dispatched(at=REQUESTED_AT + timedelta(seconds=2))
