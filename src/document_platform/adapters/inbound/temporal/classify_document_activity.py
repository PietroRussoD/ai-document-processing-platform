"""Temporal activity for deterministic document classification."""

from uuid import UUID

from temporalio import activity

from document_platform.application.commands import ClassifyDocument, ClassifyDocumentHandler
from document_platform.application.temporal_contracts import CLASSIFY_DOCUMENT_ACTIVITY


class ClassifyDocumentActivity:
    def __init__(self, classify_document: ClassifyDocumentHandler) -> None:
        self._classify_document = classify_document

    @activity.defn(name=CLASSIFY_DOCUMENT_ACTIVITY)
    async def classify_document(self, processing_run_id: str) -> str:
        result = await self._classify_document(ClassifyDocument(UUID(processing_run_id)))
        return result.document_type.value
