"""Temporal activity for embedded PDF text extraction."""

from uuid import UUID

from temporalio import activity

from document_platform.application.commands import ExtractDocumentText, ExtractDocumentTextHandler
from document_platform.application.temporal_contracts import EXTRACT_DOCUMENT_TEXT_ACTIVITY


class ExtractDocumentTextActivity:
    def __init__(self, extract_document_text: ExtractDocumentTextHandler) -> None:
        self._extract_document_text = extract_document_text

    @activity.defn(name=EXTRACT_DOCUMENT_TEXT_ACTIVITY)
    async def extract_document_text(self, processing_run_id: str) -> None:
        await self._extract_document_text(ExtractDocumentText(UUID(processing_run_id)))
