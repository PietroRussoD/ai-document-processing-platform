"""Temporal activity for embedded PDF text extraction."""

from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from document_platform.adapters.inbound.temporal.parser_activity_heartbeat import (
    parser_activity_heartbeat,
)
from document_platform.application.commands import ExtractDocumentText, ExtractDocumentTextHandler
from document_platform.application.ports import (
    EncryptedPdf,
    InvalidPdf,
    ParserExecutionFailed,
    ParserOutputExceeded,
    ParserRuntimeRejected,
    ParserRuntimeUnavailable,
    PdfPageLimitExceeded,
    PdfTextLimitExceeded,
)
from document_platform.application.temporal_contracts import EXTRACT_DOCUMENT_TEXT_ACTIVITY

_NON_RETRYABLE_PDF_FAILURES = (
    EncryptedPdf,
    InvalidPdf,
    ParserExecutionFailed,
    ParserOutputExceeded,
    PdfPageLimitExceeded,
    PdfTextLimitExceeded,
)


class ExtractDocumentTextActivity:
    def __init__(self, extract_document_text: ExtractDocumentTextHandler) -> None:
        self._extract_document_text = extract_document_text

    @activity.defn(name=EXTRACT_DOCUMENT_TEXT_ACTIVITY)
    async def extract_document_text(self, processing_run_id: str) -> None:
        try:
            async with parser_activity_heartbeat():
                await self._extract_document_text(ExtractDocumentText(UUID(processing_run_id)))
        except ParserRuntimeUnavailable as error:
            raise ApplicationError(
                "PDF parser runtime is temporarily unavailable",
                type="PARSER_RUNTIME_UNAVAILABLE",
            ) from error
        except ParserRuntimeRejected as error:
            raise ApplicationError(
                "PDF parser runtime rejected the controller request",
                type="PARSER_RUNTIME_REJECTED",
                non_retryable=True,
            ) from error
        except _NON_RETRYABLE_PDF_FAILURES as error:
            raise ApplicationError(
                "PDF extraction failed with a non-retryable error",
                type="PDF_NON_RETRYABLE_FAILURE",
                non_retryable=True,
            ) from error
