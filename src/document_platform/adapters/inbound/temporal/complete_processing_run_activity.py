"""Temporal activity for the successful completion of a processing run."""

from uuid import UUID

from temporalio import activity

from document_platform.application.commands import (
    CompleteProcessingRun,
    CompleteProcessingRunHandler,
)
from document_platform.application.temporal_contracts import COMPLETE_PROCESSING_RUN_ACTIVITY


class CompleteProcessingRunActivity:
    def __init__(self, complete_processing_run: CompleteProcessingRunHandler) -> None:
        self._complete_processing_run = complete_processing_run

    @activity.defn(name=COMPLETE_PROCESSING_RUN_ACTIVITY)
    async def complete_processing_run(self, processing_run_id: str) -> None:
        await self._complete_processing_run(CompleteProcessingRun(UUID(processing_run_id)))
