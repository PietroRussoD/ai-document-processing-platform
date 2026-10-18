"""Temporal activity for the conditional OCR fallback."""

from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from document_platform.application.commands import ExtractOcrText, ExtractOcrTextHandler
from document_platform.application.ports import (
    OcrEngineUnavailable,
    OcrExtractionFailed,
    OcrTextLimitExceeded,
    ParserRuntimeUnavailable,
)
from document_platform.application.temporal_contracts import EXTRACT_OCR_TEXT_ACTIVITY

_NON_RETRYABLE_OCR_FAILURES = (
    OcrEngineUnavailable,
    OcrExtractionFailed,
    OcrTextLimitExceeded,
)


class ExtractOcrTextActivity:
    def __init__(self, extract_ocr_text: ExtractOcrTextHandler) -> None:
        self._extract_ocr_text = extract_ocr_text

    @activity.defn(name=EXTRACT_OCR_TEXT_ACTIVITY)
    async def extract_ocr_text(self, processing_run_id: str) -> None:
        try:
            await self._extract_ocr_text(ExtractOcrText(UUID(processing_run_id)))
        except ParserRuntimeUnavailable as error:
            raise ApplicationError(
                "PDF parser runtime is temporarily unavailable",
                type="PARSER_RUNTIME_UNAVAILABLE",
            ) from error
        except _NON_RETRYABLE_OCR_FAILURES as error:
            raise ApplicationError(
                "OCR processing failed with a non-retryable error",
                type="OCR_NON_RETRYABLE_FAILURE",
                non_retryable=True,
            ) from error
