"""Temporal OCR fallback activity tests."""

from uuid import UUID

import pytest

from document_platform.adapters.inbound.temporal import ExtractOcrTextActivity
from document_platform.application.commands import ExtractOcrText, OcrTextExtractionResult

RUN_ID = UUID("73737373-7373-4373-8373-737373737373")


class RecordingExtractOcrText:
    def __init__(self) -> None:
        self.commands: list[ExtractOcrText] = []

    async def __call__(self, command: ExtractOcrText) -> OcrTextExtractionResult:
        self.commands.append(command)
        return OcrTextExtractionResult(command.processing_run_id, performed=False, replayed=False)


@pytest.mark.anyio
async def test_maps_the_temporal_argument_to_the_application_command() -> None:
    handler = RecordingExtractOcrText()
    activity = ExtractOcrTextActivity(handler)  # type: ignore[arg-type]

    await activity.extract_ocr_text(str(RUN_ID))

    assert handler.commands == [ExtractOcrText(RUN_ID)]
