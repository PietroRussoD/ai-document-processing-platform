"""Processing-run lifecycle unit tests."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from document_platform.domain.processing import (
    InvalidProcessingFailure,
    InvalidProcessingRun,
    InvalidProcessingRunTransition,
    ProcessingFailure,
    ProcessingFailureCode,
    ProcessingRun,
    ProcessingRunStatus,
    ProcessingStage,
)

RUN_ID = UUID("60a5ab35-fd9f-41bf-a007-91b07df38fec")
DOCUMENT_ID = UUID("baa4df29-707a-47f3-947f-ad79b935c400")
PREVIOUS_RUN_ID = UUID("9b0f9be2-572c-41b8-a369-df1d9f9e4c8a")
QUEUED_AT = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)


def queued_run(**overrides: object) -> ProcessingRun:
    values: dict[str, object] = {
        "run_id": RUN_ID,
        "document_id": DOCUMENT_ID,
        "queued_at": QUEUED_AT,
    }
    values.update(overrides)
    return ProcessingRun.queue(**values)  # type: ignore[arg-type]


def test_queues_an_unstarted_run() -> None:
    run = queued_run()

    assert run.status is ProcessingRunStatus.QUEUED
    assert run.started_at is None
    assert run.finished_at is None
    assert run.attempt_count == 0
    assert run.version == 0
    assert run.previous_run_id is None


def test_queues_a_reprocessing_run_with_immutable_lineage() -> None:
    run = queued_run(previous_run_id=PREVIOUS_RUN_ID)

    assert run.previous_run_id == PREVIOUS_RUN_ID


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("run_id", UUID(int=0)),
        ("document_id", UUID(int=0)),
        ("previous_run_id", UUID(int=0)),
        ("previous_run_id", RUN_ID),
        ("queued_at", datetime(2026, 9, 13, 12, 0)),
    ],
)
def test_rejects_invalid_queued_run_data(field: str, invalid_value: object) -> None:
    with pytest.raises(InvalidProcessingRun):
        queued_run(**{field: invalid_value})


def test_completes_a_run_on_its_first_attempt() -> None:
    started_at = QUEUED_AT + timedelta(seconds=1)
    completed_at = started_at + timedelta(seconds=2)

    queued = queued_run()
    running = queued.start(at=started_at)
    completed = running.complete(at=completed_at)

    assert queued.status is ProcessingRunStatus.QUEUED
    assert running.status is ProcessingRunStatus.RUNNING
    assert running.started_at == started_at
    assert running.attempt_count == 1
    assert completed.status is ProcessingRunStatus.COMPLETED
    assert completed.finished_at == completed_at
    assert completed.version == 2


def test_retries_a_run_without_changing_its_original_start_time() -> None:
    started_at = QUEUED_AT + timedelta(seconds=1)
    retry_at = QUEUED_AT + timedelta(seconds=3)

    waiting = queued_run().start(at=started_at).wait_for_retry(at=QUEUED_AT + timedelta(seconds=2))
    retried = waiting.retry(at=retry_at)

    assert retried.status is ProcessingRunStatus.RUNNING
    assert retried.started_at == started_at
    assert retried.attempt_count == 2
    assert retried.version == 3


def test_resumes_after_review_without_counting_a_retry() -> None:
    review_required = (
        queued_run()
        .start(at=QUEUED_AT + timedelta(seconds=1))
        .require_review(at=QUEUED_AT + timedelta(seconds=2))
    )

    resumed = review_required.resume_after_review(at=QUEUED_AT + timedelta(seconds=3))

    assert resumed.status is ProcessingRunStatus.RUNNING
    assert resumed.attempt_count == 1


def test_completes_a_resolved_review_without_resuming_processing() -> None:
    review_required = (
        queued_run()
        .start(at=QUEUED_AT + timedelta(seconds=1))
        .require_review(at=QUEUED_AT + timedelta(seconds=2))
    )

    completed = review_required.complete_after_review(at=QUEUED_AT + timedelta(seconds=3))

    assert completed.status is ProcessingRunStatus.COMPLETED
    assert completed.finished_at == QUEUED_AT + timedelta(seconds=3)
    assert completed.attempt_count == 1
    assert completed.version == review_required.version + 1


@pytest.mark.parametrize(
    "run",
    [
        queued_run(),
        queued_run().start(at=QUEUED_AT + timedelta(seconds=1)),
        queued_run()
        .start(at=QUEUED_AT + timedelta(seconds=1))
        .wait_for_retry(at=QUEUED_AT + timedelta(seconds=2)),
    ],
)
def test_cancels_an_active_run(run: ProcessingRun) -> None:
    cancelled_at = QUEUED_AT + timedelta(seconds=3)

    cancelled = run.cancel(at=cancelled_at)

    assert cancelled.status is ProcessingRunStatus.CANCELLED
    assert cancelled.finished_at == cancelled_at


@pytest.mark.parametrize(
    ("operation", "expected_status"),
    [
        ("complete", ProcessingRunStatus.COMPLETED),
        ("fail", ProcessingRunStatus.FAILED),
    ],
)
def test_finishes_a_running_run(operation: str, expected_status: ProcessingRunStatus) -> None:
    running = queued_run().start(at=QUEUED_AT + timedelta(seconds=1))
    finished_at = QUEUED_AT + timedelta(seconds=2)

    finished = (
        running.complete(at=finished_at)
        if operation == "complete"
        else running.fail(
            at=finished_at,
            failure=ProcessingFailure(
                stage=ProcessingStage.EMBEDDED_TEXT_EXTRACTION,
                code=ProcessingFailureCode.ACTIVITY_RETRY_EXHAUSTED,
            ),
        )
    )

    assert finished.status is expected_status
    assert finished.finished_at == finished_at


def test_records_only_bounded_evidence_for_a_terminal_failure() -> None:
    failure = ProcessingFailure(
        stage=ProcessingStage.EMBEDDED_TEXT_EXTRACTION,
        code=ProcessingFailureCode.ACTIVITY_RETRY_EXHAUSTED,
    )

    failed = (
        queued_run()
        .start(at=QUEUED_AT + timedelta(seconds=1))
        .fail(
            at=QUEUED_AT + timedelta(seconds=2),
            failure=failure,
        )
    )

    assert failed.failure == failure


def test_rejects_failed_runs_without_failure_evidence() -> None:
    running = queued_run().start(at=QUEUED_AT + timedelta(seconds=1))

    with pytest.raises(InvalidProcessingRun, match="failure evidence"):
        ProcessingRun(
            id=running.id,
            document_id=running.document_id,
            status=ProcessingRunStatus.FAILED,
            queued_at=running.queued_at,
            started_at=running.started_at,
            status_changed_at=QUEUED_AT + timedelta(seconds=2),
            finished_at=QUEUED_AT + timedelta(seconds=2),
            attempt_count=running.attempt_count,
            version=running.version + 1,
        )


def test_rejects_unbounded_failure_evidence() -> None:
    with pytest.raises(InvalidProcessingFailure, match="ProcessingStage"):
        ProcessingFailure(
            stage="embedded text extraction",  # type: ignore[arg-type]
            code=ProcessingFailureCode.ACTIVITY_RETRY_EXHAUSTED,
        )


def test_rejects_skipping_directly_from_queued_to_completed() -> None:
    with pytest.raises(
        InvalidProcessingRunTransition,
        match="cannot transition from QUEUED to COMPLETED",
    ):
        queued_run().complete(at=QUEUED_AT + timedelta(seconds=1))


def test_rejects_a_transition_with_a_backwards_timestamp() -> None:
    running = queued_run().start(at=QUEUED_AT + timedelta(seconds=2))

    with pytest.raises(InvalidProcessingRunTransition, match="must not move backwards"):
        running.wait_for_retry(at=QUEUED_AT + timedelta(seconds=1))
