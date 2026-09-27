"""Processing-workflow failure classification tests."""

from datetime import timedelta

import pytest
from temporalio.common import RetryPolicy
from temporalio.exceptions import (
    ActivityError,
    ApplicationError,
    RetryState,
    TimeoutError,
    TimeoutType,
)

import document_platform.workflows.process_business_document as workflow_module
from document_platform.application.temporal_contracts import (
    APPLY_INVOICE_VALIDATION_ACTIVITY,
    CLASSIFY_DOCUMENT_ACTIVITY,
    PROPOSE_INVOICE_FIELDS_ACTIVITY,
    RECORD_INVOICE_PROPOSAL_FAILURE_ACTIVITY,
)
from document_platform.domain.processing import (
    InvoiceProposalGenerationFailureCode,
    ProcessingFailureCode,
)
from document_platform.workflows.process_business_document import (
    ProcessBusinessDocumentWorkflow,
    classify_activity_failure,
    classify_invoice_proposal_failure,
)


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


def proposal_error(
    failure_type: str | None,
    retry_state: RetryState = RetryState.MAXIMUM_ATTEMPTS_REACHED,
) -> ActivityError:
    error = ActivityError(
        "do not parse this private message",
        scheduled_event_id=1,
        started_event_id=2,
        identity="worker",
        activity_type=PROPOSE_INVOICE_FIELDS_ACTIVITY,
        activity_id="activity-1",
        retry_state=retry_state,
    )
    if failure_type is not None:
        error.__cause__ = ApplicationError("safe", type=failure_type)
    return error


@pytest.mark.parametrize(
    ("failure_type", "retry_state", "expected"),
    [
        (
            "INVOICE_PROPOSAL_TIMEOUT",
            RetryState.MAXIMUM_ATTEMPTS_REACHED,
            InvoiceProposalGenerationFailureCode.TIMEOUT,
        ),
        (
            "INVOICE_PROPOSAL_UNAVAILABLE",
            RetryState.MAXIMUM_ATTEMPTS_REACHED,
            InvoiceProposalGenerationFailureCode.UNAVAILABLE,
        ),
        (
            "INVOICE_PROPOSAL_INVALID_RESPONSE",
            RetryState.NON_RETRYABLE_FAILURE,
            InvoiceProposalGenerationFailureCode.INVALID_RESPONSE,
        ),
        (
            None,
            RetryState.TIMEOUT,
            InvoiceProposalGenerationFailureCode.TIMEOUT,
        ),
        ("SOME_UNRELATED_FAILURE", RetryState.MAXIMUM_ATTEMPTS_REACHED, None),
    ],
)
def test_classifies_only_safe_provider_failures(
    failure_type: str | None,
    retry_state: RetryState,
    expected: InvoiceProposalGenerationFailureCode | None,
) -> None:
    assert classify_invoice_proposal_failure(proposal_error(failure_type, retry_state)) is expected


def test_classifies_an_exhausted_activity_timeout_from_its_cause() -> None:
    error = proposal_error(None)
    error.__cause__ = TimeoutError(
        "do not parse timeout details",
        type=TimeoutType.START_TO_CLOSE,
        last_heartbeat_details=(),
    )

    assert classify_invoice_proposal_failure(error) is InvoiceProposalGenerationFailureCode.TIMEOUT


@pytest.mark.anyio
async def test_runs_advisory_proposal_after_deterministic_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def patched(patch_id: str) -> bool:
        assert patch_id == "advisory-invoice-proposal-v1"
        return True

    async def execute_activity(*args: object, **kwargs: object) -> object:
        name = str(args[0])
        calls.append((name, kwargs))
        return "INVOICE" if name == CLASSIFY_DOCUMENT_ACTIVITY else None

    monkeypatch.setattr(workflow_module.workflow, "patched", patched)
    monkeypatch.setattr(workflow_module.workflow, "execute_activity", execute_activity)

    await ProcessBusinessDocumentWorkflow().run("run-1")

    names = [name for name, _ in calls]
    assert names[-2:] == [APPLY_INVOICE_VALIDATION_ACTIVITY, PROPOSE_INVOICE_FIELDS_ACTIVITY]
    assert RECORD_INVOICE_PROPOSAL_FAILURE_ACTIVITY not in names
    proposal_options = calls[-1][1]
    assert isinstance(proposal_options["retry_policy"], RetryPolicy)
    assert proposal_options["retry_policy"].maximum_attempts == 2
    assert proposal_options["start_to_close_timeout"] == timedelta(seconds=150)
    assert proposal_options["schedule_to_close_timeout"] == timedelta(minutes=5)


@pytest.mark.anyio
async def test_records_terminal_provider_failure_without_failing_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def patched(patch_id: str) -> bool:
        return True

    async def execute_activity(*args: object, **kwargs: object) -> object:
        name = str(args[0])
        calls.append((name, kwargs))
        if name == PROPOSE_INVOICE_FIELDS_ACTIVITY:
            raise proposal_error("INVOICE_PROPOSAL_UNAVAILABLE")
        return "INVOICE" if name == CLASSIFY_DOCUMENT_ACTIVITY else None

    monkeypatch.setattr(workflow_module.workflow, "patched", patched)
    monkeypatch.setattr(workflow_module.workflow, "execute_activity", execute_activity)

    await ProcessBusinessDocumentWorkflow().run("run-1")

    assert [name for name, _ in calls][-3:] == [
        APPLY_INVOICE_VALIDATION_ACTIVITY,
        PROPOSE_INVOICE_FIELDS_ACTIVITY,
        RECORD_INVOICE_PROPOSAL_FAILURE_ACTIVITY,
    ]
    assert calls[-1][1]["args"] == ["run-1", "UNAVAILABLE"]


@pytest.mark.anyio
async def test_old_workflow_branch_does_not_schedule_ai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    names: list[str] = []

    def patched(patch_id: str) -> bool:
        return False

    async def execute_activity(*args: object, **kwargs: object) -> object:
        name = str(args[0])
        names.append(name)
        return "INVOICE" if name == CLASSIFY_DOCUMENT_ACTIVITY else None

    monkeypatch.setattr(workflow_module.workflow, "patched", patched)
    monkeypatch.setattr(workflow_module.workflow, "execute_activity", execute_activity)

    await ProcessBusinessDocumentWorkflow().run("run-1")

    assert names[-1] == APPLY_INVOICE_VALIDATION_ACTIVITY
    assert PROPOSE_INVOICE_FIELDS_ACTIVITY not in names


@pytest.mark.anyio
async def test_other_document_type_does_not_schedule_ai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    names: list[str] = []

    def patched(patch_id: str) -> bool:
        raise AssertionError("AI patch must not be evaluated for non-invoices")

    async def execute_activity(*args: object, **kwargs: object) -> object:
        name = str(args[0])
        names.append(name)
        return "OTHER" if name == CLASSIFY_DOCUMENT_ACTIVITY else None

    monkeypatch.setattr(workflow_module.workflow, "patched", patched)
    monkeypatch.setattr(workflow_module.workflow, "execute_activity", execute_activity)

    await ProcessBusinessDocumentWorkflow().run("run-1")

    assert PROPOSE_INVOICE_FIELDS_ACTIVITY not in names
    assert RECORD_INVOICE_PROPOSAL_FAILURE_ACTIVITY not in names


@pytest.mark.anyio
async def test_unrecognized_ai_failure_is_not_misreported_as_provider_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    names: list[str] = []

    def patched(patch_id: str) -> bool:
        return True

    async def execute_activity(*args: object, **kwargs: object) -> object:
        name = str(args[0])
        names.append(name)
        if name == PROPOSE_INVOICE_FIELDS_ACTIVITY:
            raise proposal_error("UNRELATED_ACTIVITY_ERROR")
        return "INVOICE" if name == CLASSIFY_DOCUMENT_ACTIVITY else None

    monkeypatch.setattr(workflow_module.workflow, "patched", patched)
    monkeypatch.setattr(workflow_module.workflow, "execute_activity", execute_activity)

    with pytest.raises(ActivityError):
        await ProcessBusinessDocumentWorkflow().run("run-1")

    assert RECORD_INVOICE_PROPOSAL_FAILURE_ACTIVITY not in names
