"""Processing-workflow failure classification tests."""

import pytest
from temporalio.exceptions import ActivityError, RetryState

from document_platform.domain.processing import ProcessingFailureCode
from document_platform.workflows.process_business_document import classify_activity_failure


@pytest.mark.parametrize(
    ("retry_state", "expected"),
    [
        (RetryState.MAXIMUM_ATTEMPTS_REACHED, ProcessingFailureCode.ACTIVITY_RETRY_EXHAUSTED),
        (RetryState.NON_RETRYABLE_FAILURE, ProcessingFailureCode.NON_RETRYABLE_ACTIVITY_FAILURE),
        (RetryState.TIMEOUT, ProcessingFailureCode.ACTIVITY_TIMEOUT),
    ],
)
def test_classifies_terminal_activity_failures_without_using_messages(
    retry_state: RetryState,
    expected: ProcessingFailureCode,
) -> None:
    error = ActivityError(
        "sensitive upstream exception detail",
        scheduled_event_id=1,
        started_event_id=2,
        identity="worker",
        activity_type="extract-document-text",
        activity_id="activity-1",
        retry_state=retry_state,
    )

    assert classify_activity_failure(error) is expected
