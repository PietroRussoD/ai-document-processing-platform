"""Temporal embedded-text extraction activity tests."""

from uuid import UUID

import pytest
from temporalio.exceptions import ApplicationError

from document_platform.adapters.inbound.temporal import ExtractDocumentTextActivity
from document_platform.application.commands import DocumentTextExtracted, ExtractDocumentText
from document_platform.application.ports import (
    EncryptedPdf,
    InvalidPdf,
    ParserRuntimeUnavailable,
    PdfPageLimitExceeded,
    PdfTextLimitExceeded,
)

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


@pytest.mark.anyio
async def test_keeps_parser_runtime_unavailability_retryable() -> None:
    class UnavailableExtractDocumentText:
        async def __call__(self, command: ExtractDocumentText) -> DocumentTextExtracted:
            raise ParserRuntimeUnavailable("private connection detail")

    activity = ExtractDocumentTextActivity(UnavailableExtractDocumentText())  # type: ignore[arg-type]

    with pytest.raises(ApplicationError) as raised:
        await activity.extract_document_text(str(RUN_ID))

    assert raised.value.type == "PARSER_RUNTIME_UNAVAILABLE"
    assert raised.value.non_retryable is False
    assert "private connection detail" not in str(raised.value)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure",
    [
        EncryptedPdf("private PDF detail"),
        InvalidPdf("private PDF detail"),
        PdfPageLimitExceeded(50),
        PdfTextLimitExceeded(100),
    ],
)
async def test_marks_known_pdf_content_failures_non_retryable(failure: Exception) -> None:
    class FailingExtractDocumentText:
        async def __call__(self, command: ExtractDocumentText) -> DocumentTextExtracted:
            raise failure

    activity = ExtractDocumentTextActivity(FailingExtractDocumentText())  # type: ignore[arg-type]

    with pytest.raises(ApplicationError) as raised:
        await activity.extract_document_text(str(RUN_ID))

    assert raised.value.type == "PDF_NON_RETRYABLE_FAILURE"
    assert raised.value.non_retryable is True
    assert "private PDF detail" not in str(raised.value)
