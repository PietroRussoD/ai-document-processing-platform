"""Temporal activity that persists safe terminal processing failure evidence."""

from uuid import UUID

from temporalio import activity

from document_platform.application.commands import (
    RecordProcessingRunFailure,
    RecordProcessingRunFailureHandler,
)
from document_platform.application.temporal_contracts import RECORD_PROCESSING_RUN_FAILURE_ACTIVITY
from document_platform.domain.processing import (
    ProcessingFailure,
    ProcessingFailureCode,
    ProcessingStage,
)


class RecordProcessingRunFailureActivity:
    def __init__(self, record_processing_run_failure: RecordProcessingRunFailureHandler) -> None:
        self._record_processing_run_failure = record_processing_run_failure

    @activity.defn(name=RECORD_PROCESSING_RUN_FAILURE_ACTIVITY)
    async def record_processing_run_failure(
        self,
        processing_run_id: str,
        stage: str,
        failure_code: str,
    ) -> None:
        await self._record_processing_run_failure(
            RecordProcessingRunFailure(
                processing_run_id=UUID(processing_run_id),
                failure=ProcessingFailure(
                    stage=ProcessingStage(stage),
                    code=ProcessingFailureCode(failure_code),
                ),
            )
        )
