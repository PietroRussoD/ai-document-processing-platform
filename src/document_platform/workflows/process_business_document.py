"""Durable orchestration for one business-document processing run."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from document_platform.application.temporal_contracts import (
    CLASSIFY_DOCUMENT_ACTIVITY,
    EXTRACT_DOCUMENT_TEXT_ACTIVITY,
    EXTRACT_OCR_TEXT_ACTIVITY,
    PROCESS_BUSINESS_DOCUMENT_WORKFLOW,
    SELECT_PROCESSING_TEXT_ACTIVITY,
    START_PROCESSING_RUN_ACTIVITY,
)


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
        await workflow.execute_activity(
            EXTRACT_DOCUMENT_TEXT_ACTIVITY,
            processing_run_id,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        await workflow.execute_activity(
            EXTRACT_OCR_TEXT_ACTIVITY,
            processing_run_id,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        await workflow.execute_activity(
            SELECT_PROCESSING_TEXT_ACTIVITY,
            processing_run_id,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        await workflow.execute_activity(
            CLASSIFY_DOCUMENT_ACTIVITY,
            processing_run_id,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
