"""Temporal processing-text selection activity tests."""

from uuid import UUID

import pytest

from document_platform.adapters.inbound.temporal import SelectProcessingTextActivity
from document_platform.application.commands import ProcessingTextSelected, SelectProcessingText

RUN_ID = UUID("92929292-9292-4292-8292-929292929292")


class RecordingSelectProcessingText:
    def __init__(self) -> None:
        self.commands: list[SelectProcessingText] = []

    async def __call__(self, command: SelectProcessingText) -> ProcessingTextSelected:
        self.commands.append(command)
        return ProcessingTextSelected(command.processing_run_id, replayed=False)


@pytest.mark.anyio
async def test_maps_the_temporal_argument_to_the_application_command() -> None:
    handler = RecordingSelectProcessingText()
    activity = SelectProcessingTextActivity(handler)  # type: ignore[arg-type]

    await activity.select_processing_text(str(RUN_ID))

    assert handler.commands == [SelectProcessingText(RUN_ID)]
