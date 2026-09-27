"""Durable orchestration for one business-document processing run."""

from datetime import timedelta
from typing import cast

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError, RetryState, TimeoutError

from document_platform.application.temporal_contracts import (
    APPLY_INVOICE_VALIDATION_ACTIVITY,
    CLASSIFY_DOCUMENT_ACTIVITY,
    COMPLETE_PROCESSING_RUN_ACTIVITY,
    EXTRACT_DOCUMENT_TEXT_ACTIVITY,
    EXTRACT_INVOICE_ACTIVITY,
    EXTRACT_OCR_TEXT_ACTIVITY,
    INVOICE_PROPOSAL_FAILURE_TYPE_PREFIX,
    PROCESS_BUSINESS_DOCUMENT_WORKFLOW,
    PROPOSE_INVOICE_FIELDS_ACTIVITY,
    RECORD_INVOICE_PROPOSAL_FAILURE_ACTIVITY,
    RECORD_PROCESSING_RUN_FAILURE_ACTIVITY,
    SELECT_PROCESSING_TEXT_ACTIVITY,
    START_PROCESSING_RUN_ACTIVITY,
    VALIDATE_INVOICE_ACTIVITY,
)
from document_platform.domain.processing import (
    InvoiceProposalGenerationFailureCode,
    ProcessingFailureCode,
    ProcessingStage,
)

_ACTIVITY_RETRY_POLICY = RetryPolicy(maximum_attempts=3)
_FAILURE_RECORDING_RETRY_POLICY = RetryPolicy(maximum_attempts=3)
_PROPOSAL_RETRY_POLICY = RetryPolicy(maximum_attempts=2)
_ADVISORY_PROPOSAL_PATCH = "advisory-invoice-proposal-v1"


@workflow.defn(name=PROCESS_BUSINESS_DOCUMENT_WORKFLOW)
class ProcessBusinessDocumentWorkflow:
    @workflow.run
    async def run(self, processing_run_id: str) -> None:
        await workflow.execute_activity(
            START_PROCESSING_RUN_ACTIVITY,
            processing_run_id,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_ACTIVITY_RETRY_POLICY,
        )
        await _execute_processing_stage(
            EXTRACT_DOCUMENT_TEXT_ACTIVITY,
            processing_run_id,
            ProcessingStage.EMBEDDED_TEXT_EXTRACTION,
            timeout=timedelta(minutes=2),
        )
        await _execute_processing_stage(
            EXTRACT_OCR_TEXT_ACTIVITY,
            processing_run_id,
            ProcessingStage.OCR_TEXT_EXTRACTION,
            timeout=timedelta(minutes=5),
        )
        await _execute_processing_stage(
            SELECT_PROCESSING_TEXT_ACTIVITY,
            processing_run_id,
            ProcessingStage.TEXT_SELECTION,
            timeout=timedelta(seconds=30),
        )
        document_type = cast(
            str,
            await _execute_processing_stage(
                CLASSIFY_DOCUMENT_ACTIVITY,
                processing_run_id,
                ProcessingStage.CLASSIFICATION,
                timeout=timedelta(seconds=30),
            ),
        )
        if document_type == "INVOICE":
            await _execute_processing_stage(
                EXTRACT_INVOICE_ACTIVITY,
                processing_run_id,
                ProcessingStage.INVOICE_EXTRACTION,
                timeout=timedelta(seconds=30),
            )
            await _execute_processing_stage(
                VALIDATE_INVOICE_ACTIVITY,
                processing_run_id,
                ProcessingStage.INVOICE_VALIDATION,
                timeout=timedelta(seconds=30),
            )
            await _execute_processing_stage(
                APPLY_INVOICE_VALIDATION_ACTIVITY,
                processing_run_id,
                ProcessingStage.VALIDATION_APPLICATION,
                timeout=timedelta(seconds=30),
            )
            if workflow.patched(_ADVISORY_PROPOSAL_PATCH):
                await _execute_advisory_proposal(processing_run_id)
        else:
            await _execute_processing_stage(
                COMPLETE_PROCESSING_RUN_ACTIVITY,
                processing_run_id,
                ProcessingStage.COMPLETION,
                timeout=timedelta(seconds=30),
            )


async def _execute_processing_stage(
    activity_name: str,
    processing_run_id: str,
    stage: ProcessingStage,
    *,
    timeout: timedelta,
) -> object:
    try:
        return await workflow.execute_activity(
            activity_name,
            processing_run_id,
            start_to_close_timeout=timeout,
            retry_policy=_ACTIVITY_RETRY_POLICY,
        )
    except ActivityError as error:
        await workflow.execute_activity(
            RECORD_PROCESSING_RUN_FAILURE_ACTIVITY,
            args=[processing_run_id, stage.value, classify_activity_failure(error).value],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_FAILURE_RECORDING_RETRY_POLICY,
        )
        raise


def classify_activity_failure(error: ActivityError) -> ProcessingFailureCode:
    if error.retry_state is RetryState.NON_RETRYABLE_FAILURE:
        return ProcessingFailureCode.NON_RETRYABLE_ACTIVITY_FAILURE
    if error.retry_state is RetryState.TIMEOUT:
        return ProcessingFailureCode.ACTIVITY_TIMEOUT
    return ProcessingFailureCode.ACTIVITY_RETRY_EXHAUSTED


async def _execute_advisory_proposal(processing_run_id: str) -> None:
    try:
        await workflow.execute_activity(
            PROPOSE_INVOICE_FIELDS_ACTIVITY,
            processing_run_id,
            start_to_close_timeout=timedelta(seconds=150),
            schedule_to_close_timeout=timedelta(minutes=5),
            retry_policy=_PROPOSAL_RETRY_POLICY,
        )
    except ActivityError as error:
        code = classify_invoice_proposal_failure(error)
        if code is None:
            raise
        await workflow.execute_activity(
            RECORD_INVOICE_PROPOSAL_FAILURE_ACTIVITY,
            args=[processing_run_id, code.value],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_FAILURE_RECORDING_RETRY_POLICY,
        )


def classify_invoice_proposal_failure(
    error: ActivityError,
) -> InvoiceProposalGenerationFailureCode | None:
    cause = error.cause
    if (
        isinstance(cause, ApplicationError)
        and cause.type is not None
        and cause.type.startswith(INVOICE_PROPOSAL_FAILURE_TYPE_PREFIX)
    ):
        raw_code = cause.type.removeprefix(INVOICE_PROPOSAL_FAILURE_TYPE_PREFIX)
        try:
            return InvoiceProposalGenerationFailureCode(raw_code)
        except ValueError:
            return None
    if isinstance(cause, TimeoutError) or error.retry_state is RetryState.TIMEOUT:
        return InvoiceProposalGenerationFailureCode.TIMEOUT
    return None
