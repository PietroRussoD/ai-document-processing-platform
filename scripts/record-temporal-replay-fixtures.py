"""Record synthetic histories for the workflow replay compatibility tests."""

import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import cast
from uuid import uuid4

from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from document_platform.application import temporal_contracts as contracts
from document_platform.workflows.process_business_document import ProcessBusinessDocumentWorkflow


@activity.defn(name=contracts.START_PROCESSING_RUN_ACTIVITY)
async def start_processing_run(_run_id: str) -> None:
    pass


@activity.defn(name=contracts.EXTRACT_DOCUMENT_TEXT_ACTIVITY)
async def extract_document_text(_run_id: str) -> None:
    pass


@activity.defn(name=contracts.EXTRACT_OCR_TEXT_ACTIVITY)
async def extract_ocr_text(_run_id: str) -> None:
    pass


@activity.defn(name=contracts.SELECT_PROCESSING_TEXT_ACTIVITY)
async def select_processing_text(_run_id: str) -> None:
    pass


@activity.defn(name=contracts.CLASSIFY_DOCUMENT_ACTIVITY)
async def classify_document(run_id: str) -> str:
    return "INVOICE" if run_id == "synthetic-invoice" else "OTHER"


@activity.defn(name=contracts.EXTRACT_INVOICE_ACTIVITY)
async def extract_invoice(_run_id: str) -> None:
    pass


@activity.defn(name=contracts.VALIDATE_INVOICE_ACTIVITY)
async def validate_invoice(_run_id: str) -> None:
    pass


@activity.defn(name=contracts.APPLY_INVOICE_VALIDATION_ACTIVITY)
async def apply_invoice_validation(_run_id: str) -> None:
    pass


@activity.defn(name=contracts.PROPOSE_INVOICE_FIELDS_ACTIVITY)
async def propose_invoice_fields(_run_id: str) -> None:
    pass


@activity.defn(name=contracts.RECORD_INVOICE_PROPOSAL_FAILURE_ACTIVITY)
async def record_invoice_proposal_failure(_run_id: str, _failure_code: str) -> None:
    pass


@activity.defn(name=contracts.COMPLETE_PROCESSING_RUN_ACTIVITY)
async def complete_processing_run(_run_id: str) -> None:
    pass


ACTIVITIES = [
    start_processing_run,
    extract_document_text,
    extract_ocr_text,
    select_processing_text,
    classify_document,
    extract_invoice,
    validate_invoice,
    apply_invoice_validation,
    propose_invoice_fields,
    record_invoice_proposal_failure,
    complete_processing_run,
]
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "temporal"


def remove_worker_identity(value: object) -> object:
    if isinstance(value, dict):
        fields = cast(dict[str, object], value)
        return {
            key: (
                "fixture-worker"
                if key == "identity"
                else "fixture-sticky-queue"
                if key == "name" and isinstance(item, str) and "@" in item
                else remove_worker_identity(item)
            )
            for key, item in fields.items()
        }
    if isinstance(value, list):
        return [remove_worker_identity(item) for item in cast(list[object], value)]
    return value


async def main(fixture_set: str) -> None:
    run_ids = ("synthetic-invoice", "synthetic-other")
    fixture_paths = [FIXTURE_DIR / f"{fixture_set}-{run_id}.json" for run_id in run_ids]
    existing_paths = [path for path in fixture_paths if path.exists()]
    if existing_paths:
        paths = ", ".join(str(path) for path in existing_paths)
        raise FileExistsError(f"Refusing to overwrite existing replay fixtures: {paths}")

    async with await WorkflowEnvironment.start_local() as environment:  # pyright: ignore[reportUnknownMemberType]
        task_queue = f"replay-fixtures-{uuid4()}"
        async with Worker(
            environment.client,
            task_queue=task_queue,
            workflows=[ProcessBusinessDocumentWorkflow],
            activities=ACTIVITIES,
        ):
            FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
            for run_id in run_ids:
                handle = await environment.client.start_workflow(
                    ProcessBusinessDocumentWorkflow.run,
                    run_id,
                    id=f"replay-baseline-{run_id}",
                    task_queue=task_queue,
                )
                await handle.result()
                history = await handle.fetch_history()
                sanitized = remove_worker_identity(json.loads(history.to_json()))
                (FIXTURE_DIR / f"{fixture_set}-{run_id}.json").write_text(
                    json.dumps(sanitized) + "\n"
                )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture-set",
        default="current",
        help="prefix for generated fixture files (for example, v1.2.0)",
    )
    args = parser.parse_args()
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", args.fixture_set) is None:
        parser.error("--fixture-set may contain only letters, digits, dots, and hyphens")
    return args


if __name__ == "__main__":
    asyncio.run(main(parse_args().fixture_set))
