"""Temporal activity for the conditional OCR fallback."""

import logging
import os
from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from document_platform.adapters.inbound.temporal.parser_activity_heartbeat import (
    parser_activity_heartbeat,
)
from document_platform.application.commands import ExtractOcrText, ExtractOcrTextHandler
from document_platform.application.ports import (
    OcrEngineUnavailable,
    OcrExtractionFailed,
    OcrTextLimitExceeded,
    ParserExecutionFailed,
    ParserOutputExceeded,
    ParserRuntimeRejected,
    ParserRuntimeUnavailable,
)
from document_platform.application.temporal_contracts import EXTRACT_OCR_TEXT_ACTIVITY

_NON_RETRYABLE_OCR_FAILURES = (
    OcrEngineUnavailable,
    OcrExtractionFailed,
    ParserExecutionFailed,
    ParserOutputExceeded,
    OcrTextLimitExceeded,
)
_logger = logging.getLogger(__name__)


class ExtractOcrTextActivity:
    def __init__(
        self,
        extract_ocr_text: ExtractOcrTextHandler,
        *,
        crash_after_persist_on_first_attempt: bool = False,
    ) -> None:
        self._extract_ocr_text = extract_ocr_text
        self._crash_after_persist_on_first_attempt = crash_after_persist_on_first_attempt

    @activity.defn(name=EXTRACT_OCR_TEXT_ACTIVITY)
    async def extract_ocr_text(self, processing_run_id: str) -> None:
        try:
            async with parser_activity_heartbeat():
                await self._extract_ocr_text(ExtractOcrText(UUID(processing_run_id)))
                if self._crash_after_persist_on_first_attempt and activity.info().attempt == 1:
                    _logger.warning("Fault injection: crashing after OCR result persistence")
                    os._exit(86)
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
        except _NON_RETRYABLE_OCR_FAILURES as error:
            raise ApplicationError(
                "OCR processing failed with a non-retryable error",
                type="OCR_NON_RETRYABLE_FAILURE",
                non_retryable=True,
            ) from error
