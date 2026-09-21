"""Temporal terminal-failure activity tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from document_platform.adapters.inbound.temporal import RecordProcessingRunFailureActivity
from document_platform.application.commands import (
    ProcessingRunFailureRecorded,
    RecordProcessingRunFailure,
)
from document_platform.domain.processing import (
    ProcessingFailure,
    ProcessingFailureCode,
    ProcessingStage,
)

RUN_ID = UUID("d3d3d3d3-d3d3-43d3-83d3-d3d3d3d3d3d3")


class RecordingFailureHandler:
    def __init__(self) -> None:
        self.commands: list[RecordProcessingRunFailure] = []

    async def __call__(self, command: RecordProcessingRunFailure) -> ProcessingRunFailureRecorded:
        self.commands.append(command)
        return ProcessingRunFailureRecorded(
            command.processing_run_id, datetime(2026, 9, 21, tzinfo=UTC), False
        )


@pytest.mark.anyio
async def test_maps_temporal_arguments_to_bounded_failure_evidence() -> None:
    handler = RecordingFailureHandler()
    activity = RecordProcessingRunFailureActivity(handler)  # type: ignore[arg-type]

    await activity.record_processing_run_failure(
        str(RUN_ID),
        ProcessingStage.EMBEDDED_TEXT_EXTRACTION.value,
        ProcessingFailureCode.ACTIVITY_RETRY_EXHAUSTED.value,
    )

    assert handler.commands == [
        RecordProcessingRunFailure(
            RUN_ID,
            ProcessingFailure(
                stage=ProcessingStage.EMBEDDED_TEXT_EXTRACTION,
                code=ProcessingFailureCode.ACTIVITY_RETRY_EXHAUSTED,
            ),
        )
    ]
