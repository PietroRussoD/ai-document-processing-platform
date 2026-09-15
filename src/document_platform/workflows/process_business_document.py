"""Durable orchestration for one business-document processing run."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from document_platform.application.ports.workflow_starter import PROCESS_BUSINESS_DOCUMENT_WORKFLOW

START_PROCESSING_RUN_ACTIVITY = "start-processing-run"


@workflow.defn(name=PROCESS_BUSINESS_DOCUMENT_WORKFLOW)
class ProcessBusinessDocumentWorkflow:
    @workflow.run
    async def run(self, processing_run_id: str) -> None:
        await workflow.execute_activity(
            START_PROCESSING_RUN_ACTIVITY,
            processing_run_id,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
