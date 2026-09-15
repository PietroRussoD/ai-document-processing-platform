"""Temporal embedded-text extraction activity tests."""

from uuid import UUID

import pytest

from document_platform.adapters.inbound.temporal import ExtractDocumentTextActivity
from document_platform.application.commands import DocumentTextExtracted, ExtractDocumentText

RUN_ID = UUID("53535353-5353-4353-8353-535353535353")


class RecordingExtractDocumentText:
    def __init__(self) -> None:
        self.commands: list[ExtractDocumentText] = []

    async def __call__(self, command: ExtractDocumentText) -> DocumentTextExtracted:
        self.commands.append(command)
        return DocumentTextExtracted(command.processing_run_id, 0, 0, False)


@pytest.mark.anyio
async def test_maps_the_temporal_argument_to_the_application_command() -> None:
    handler = RecordingExtractDocumentText()
    activity = ExtractDocumentTextActivity(handler)  # type: ignore[arg-type]

    await activity.extract_document_text(str(RUN_ID))

    assert handler.commands == [ExtractDocumentText(RUN_ID)]
