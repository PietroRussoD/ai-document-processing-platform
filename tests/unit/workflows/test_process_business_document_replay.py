"""Protect the workflow command sequence against incompatible edits."""

import asyncio
from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from document_platform.workflows.process_business_document import ProcessBusinessDocumentWorkflow

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "temporal"
FIXTURES = sorted(FIXTURE_DIR.glob("*-synthetic-*.json"))


@pytest.mark.parametrize("fixture_path", FIXTURES, ids=lambda path: path.stem)
def test_replays_saved_workflow_history(fixture_path: Path) -> None:
    history = WorkflowHistory.from_json(
        fixture_path.stem,
        fixture_path.read_text(),
    )

    asyncio.run(Replayer(workflows=[ProcessBusinessDocumentWorkflow]).replay_workflow(history))
