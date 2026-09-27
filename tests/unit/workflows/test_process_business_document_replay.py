"""Protect the workflow command sequence against incompatible edits."""

import asyncio
from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from document_platform.workflows.process_business_document import ProcessBusinessDocumentWorkflow

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "temporal"


@pytest.mark.parametrize("scenario", ["synthetic-invoice", "synthetic-other"])
def test_replays_v0_9_workflow_history(scenario: str) -> None:
    history = WorkflowHistory.from_json(
        scenario,
        (FIXTURE_DIR / f"{scenario}.json").read_text(),
    )

    asyncio.run(Replayer(workflows=[ProcessBusinessDocumentWorkflow]).replay_workflow(history))
