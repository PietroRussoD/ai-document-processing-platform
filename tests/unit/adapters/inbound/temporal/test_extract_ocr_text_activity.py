"""Temporal OCR fallback activity tests."""

from uuid import UUID

import pytest
from temporalio.exceptions import ApplicationError

from document_platform.adapters.inbound.temporal import ExtractOcrTextActivity
from document_platform.application.commands import ExtractOcrText, OcrTextExtractionResult
from document_platform.application.ports import (
    OcrEngineUnavailable,
    OcrExtractionFailed,
    OcrTextLimitExceeded,
    ParserExecutionFailed,
    ParserOutputExceeded,
    ParserRuntimeRejected,
    ParserRuntimeUnavailable,
)

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


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure",
    [
        OcrEngineUnavailable("local detail"),
        OcrExtractionFailed("document detail"),
        OcrTextLimitExceeded(100),
        ParserExecutionFailed("parser returned a failure status"),
        ParserOutputExceeded("parser output exceeded its configured limit"),
    ],
)
async def test_marks_known_ocr_failures_non_retryable(failure: Exception) -> None:
    class FailingExtractOcrText:
        async def __call__(self, command: ExtractOcrText) -> OcrTextExtractionResult:
            raise failure

    activity = ExtractOcrTextActivity(FailingExtractOcrText())  # type: ignore[arg-type]

    with pytest.raises(ApplicationError) as raised:
        await activity.extract_ocr_text(str(RUN_ID))

    assert raised.value.non_retryable is True
    assert raised.value.type == "OCR_NON_RETRYABLE_FAILURE"
    assert "document detail" not in str(raised.value)


@pytest.mark.anyio
async def test_keeps_parser_runtime_unavailability_retryable() -> None:
    class UnavailableExtractOcrText:
        async def __call__(self, command: ExtractOcrText) -> OcrTextExtractionResult:
            raise ParserRuntimeUnavailable("private connection detail")

    activity = ExtractOcrTextActivity(UnavailableExtractOcrText())  # type: ignore[arg-type]

    with pytest.raises(ApplicationError) as raised:
        await activity.extract_ocr_text(str(RUN_ID))

    assert raised.value.type == "PARSER_RUNTIME_UNAVAILABLE"
    assert raised.value.non_retryable is False
    assert "private connection detail" not in str(raised.value)


@pytest.mark.anyio
async def test_marks_parser_runtime_rejection_non_retryable() -> None:
    class RejectedExtractOcrText:
        async def __call__(self, command: ExtractOcrText) -> OcrTextExtractionResult:
            raise ParserRuntimeRejected("private authorization detail")

    activity = ExtractOcrTextActivity(RejectedExtractOcrText())  # type: ignore[arg-type]

    with pytest.raises(ApplicationError) as raised:
        await activity.extract_ocr_text(str(RUN_ID))

    assert raised.value.type == "PARSER_RUNTIME_REJECTED"
    assert raised.value.non_retryable is True
    assert "private authorization detail" not in str(raised.value)
