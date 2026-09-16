"""Temporal activity for canonical processing-text selection."""

from uuid import UUID

from temporalio import activity

from document_platform.application.commands import SelectProcessingText, SelectProcessingTextHandler
from document_platform.application.temporal_contracts import SELECT_PROCESSING_TEXT_ACTIVITY


class SelectProcessingTextActivity:
    def __init__(self, select_processing_text: SelectProcessingTextHandler) -> None:
        self._select_processing_text = select_processing_text

    @activity.defn(name=SELECT_PROCESSING_TEXT_ACTIVITY)
    async def select_processing_text(self, processing_run_id: str) -> None:
        await self._select_processing_text(SelectProcessingText(UUID(processing_run_id)))
