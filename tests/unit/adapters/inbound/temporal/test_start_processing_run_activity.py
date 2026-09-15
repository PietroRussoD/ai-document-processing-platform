"""Temporal initial-processing activity tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from document_platform.adapters.inbound.temporal import StartProcessingRunActivity
from document_platform.application.commands import ProcessingRunStarted, StartProcessingRun

RUN_ID = UUID("43434343-4343-4343-8343-434343434343")


class RecordingStartProcessingRun:
    def __init__(self) -> None:
        self.commands: list[StartProcessingRun] = []

    async def __call__(self, command: StartProcessingRun) -> ProcessingRunStarted:
        self.commands.append(command)
        return ProcessingRunStarted(
            command.processing_run_id,
            datetime(2026, 9, 15, tzinfo=UTC),
            False,
        )


@pytest.mark.anyio
async def test_maps_the_temporal_argument_to_the_application_command() -> None:
    handler = RecordingStartProcessingRun()
    activity = StartProcessingRunActivity(handler)  # type: ignore[arg-type]

    await activity.start_processing_run(str(RUN_ID))

    assert handler.commands == [StartProcessingRun(RUN_ID)]
