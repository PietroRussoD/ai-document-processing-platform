"""Temporal activity for the conditional OCR fallback."""

from uuid import UUID

from temporalio import activity

from document_platform.application.commands import ExtractOcrText, ExtractOcrTextHandler
from document_platform.application.temporal_contracts import EXTRACT_OCR_TEXT_ACTIVITY


class ExtractOcrTextActivity:
    def __init__(self, extract_ocr_text: ExtractOcrTextHandler) -> None:
        self._extract_ocr_text = extract_ocr_text

    @activity.defn(name=EXTRACT_OCR_TEXT_ACTIVITY)
    async def extract_ocr_text(self, processing_run_id: str) -> None:
        await self._extract_ocr_text(ExtractOcrText(UUID(processing_run_id)))
