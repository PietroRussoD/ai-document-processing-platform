"""Temporal activity for the first processing-run state transition."""

from uuid import UUID

from temporalio import activity

from document_platform.application.commands import StartProcessingRun, StartProcessingRunHandler

START_PROCESSING_RUN_ACTIVITY = "start-processing-run"


class StartProcessingRunActivity:
    def __init__(self, start_processing_run: StartProcessingRunHandler) -> None:
        self._start_processing_run = start_processing_run

    @activity.defn(name=START_PROCESSING_RUN_ACTIVITY)
    async def start_processing_run(self, processing_run_id: str) -> None:
        await self._start_processing_run(StartProcessingRun(UUID(processing_run_id)))
