"""Temporal processing-run completion activity tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from document_platform.adapters.inbound.temporal import CompleteProcessingRunActivity
from document_platform.application.commands import CompleteProcessingRun, ProcessingRunCompleted

RUN_ID = UUID("b3b3b3b3-b3b3-43b3-83b3-b3b3b3b3b3b3")


class RecordingCompleteProcessingRun:
    def __init__(self) -> None:
        self.commands: list[CompleteProcessingRun] = []

    async def __call__(self, command: CompleteProcessingRun) -> ProcessingRunCompleted:
        self.commands.append(command)
        return ProcessingRunCompleted(
            command.processing_run_id,
            datetime(2026, 9, 16, tzinfo=UTC),
            False,
        )


@pytest.mark.anyio
async def test_maps_the_temporal_argument_to_the_application_command() -> None:
    handler = RecordingCompleteProcessingRun()
    activity = CompleteProcessingRunActivity(handler)  # type: ignore[arg-type]

    await activity.complete_processing_run(str(RUN_ID))

    assert handler.commands == [CompleteProcessingRun(RUN_ID)]
