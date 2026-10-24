"""Verify Temporal retries parser runtime outages but not deterministic failures."""

import asyncio

from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from document_platform.application import temporal_contracts as contracts
from document_platform.workflows.process_business_document import ProcessBusinessDocumentWorkflow

_OCR_ATTEMPTS: dict[str, list[int]] = {}
_RECORDED_FAILURES: list[tuple[str, str, str]] = []


@activity.defn(name=contracts.START_PROCESSING_RUN_ACTIVITY)
async def start_processing_run(_run_id: str) -> None:
    pass


@activity.defn(name=contracts.EXTRACT_DOCUMENT_TEXT_ACTIVITY)
async def extract_document_text(_run_id: str) -> None:
    pass


@activity.defn(name=contracts.EXTRACT_OCR_TEXT_ACTIVITY)
async def extract_ocr_text(run_id: str) -> None:
    attempt = activity.info().attempt
    _OCR_ATTEMPTS.setdefault(run_id, []).append(attempt)
    if run_id == "transient-parser-outage" and attempt == 1:
        raise ApplicationError(
            "temporary parser outage",
            type="PARSER_RUNTIME_UNAVAILABLE",
        )
    if run_id == "deterministic-parser-failure":
        raise ApplicationError(
            "deterministic parser failure",
            type="OCR_NON_RETRYABLE_FAILURE",
            non_retryable=True,
        )


@activity.defn(name=contracts.SELECT_PROCESSING_TEXT_ACTIVITY)
async def select_processing_text(_run_id: str) -> None:
    pass


@activity.defn(name=contracts.CLASSIFY_DOCUMENT_ACTIVITY)
async def classify_document(_run_id: str) -> str:
    return "OTHER"


@activity.defn(name=contracts.COMPLETE_PROCESSING_RUN_ACTIVITY)
async def complete_processing_run(_run_id: str) -> None:
    pass


@activity.defn(name=contracts.RECORD_PROCESSING_RUN_FAILURE_ACTIVITY)
async def record_processing_run_failure(run_id: str, stage: str, failure: str) -> None:
    _RECORDED_FAILURES.append((run_id, stage, failure))


ACTIVITIES = [
    start_processing_run,
    extract_document_text,
    extract_ocr_text,
    select_processing_text,
    classify_document,
    complete_processing_run,
    record_processing_run_failure,
]


async def verify() -> None:
    _OCR_ATTEMPTS.clear()
    _RECORDED_FAILURES.clear()
    environment = await WorkflowEnvironment.start_time_skipping()  # pyright: ignore[reportUnknownMemberType]
    async with environment:
        task_queue = "parser-retry-verification"
        async with Worker(
            environment.client,
            task_queue=task_queue,
            workflows=[ProcessBusinessDocumentWorkflow],
            activities=ACTIVITIES,
        ):
            await environment.client.execute_workflow(
                ProcessBusinessDocumentWorkflow.run,
                "transient-parser-outage",
                id="verify-parser-transient-retry",
                task_queue=task_queue,
            )
            if _OCR_ATTEMPTS.get("transient-parser-outage") != [1, 2]:
                raise AssertionError(
                    "A temporary parser outage did not recover on the second OCR attempt: "
                    f"{_OCR_ATTEMPTS.get('transient-parser-outage')}"
                )

            try:
                await environment.client.execute_workflow(
                    ProcessBusinessDocumentWorkflow.run,
                    "deterministic-parser-failure",
                    id="verify-parser-deterministic-failure",
                    task_queue=task_queue,
                )
            except WorkflowFailureError:
                pass
            else:
                raise AssertionError("A deterministic parser failure unexpectedly succeeded")

    if _OCR_ATTEMPTS.get("deterministic-parser-failure") != [1]:
        raise AssertionError(
            "A deterministic parser failure was retried: "
            f"{_OCR_ATTEMPTS.get('deterministic-parser-failure')}"
        )
    if len(_RECORDED_FAILURES) != 1 or _RECORDED_FAILURES[0][0] != "deterministic-parser-failure":
        raise AssertionError(f"Unexpected terminal failure records: {_RECORDED_FAILURES}")
    print(
        "Temporal parser retry verification passed: transient outage recovered on attempt 2; "
        "deterministic failure stopped after attempt 1.",
        flush=True,
    )


if __name__ == "__main__":
    asyncio.run(verify())
