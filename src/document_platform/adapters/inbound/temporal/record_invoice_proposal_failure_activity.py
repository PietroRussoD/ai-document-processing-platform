"""Temporal activity for a terminal advisory model failure."""

from uuid import UUID

from temporalio import activity

from document_platform.application.commands import (
    RecordInvoiceProposalFailure,
    RecordInvoiceProposalFailureHandler,
)
from document_platform.application.temporal_contracts import (
    RECORD_INVOICE_PROPOSAL_FAILURE_ACTIVITY,
)
from document_platform.domain.processing import (
    InvoiceModelProvider,
    InvoiceProposalGenerationFailureCode,
)


class RecordInvoiceProposalFailureActivity:
    def __init__(
        self,
        record_failure: RecordInvoiceProposalFailureHandler,
        *,
        provider: InvoiceModelProvider,
        model_reference: str,
    ) -> None:
        self._record_failure = record_failure
        self._provider = provider
        self._model_reference = model_reference

    @activity.defn(name=RECORD_INVOICE_PROPOSAL_FAILURE_ACTIVITY)
    async def record_invoice_proposal_failure(self, processing_run_id: str, code: str) -> None:
        await self._record_failure(
            RecordInvoiceProposalFailure(
                processing_run_id=UUID(processing_run_id),
                provider=self._provider,
                model_reference=self._model_reference,
                code=InvoiceProposalGenerationFailureCode(code),
            )
        )
