"""Temporal activity for advisory invoice field proposals."""

import asyncio
from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from document_platform.application.commands import ProposeInvoiceFields, ProposeInvoiceFieldsHandler
from document_platform.application.ports import InvoiceProposalGenerationFailed
from document_platform.application.temporal_contracts import (
    INVOICE_PROPOSAL_FAILURE_TYPE_PREFIX,
    PROPOSE_INVOICE_FIELDS_ACTIVITY,
)
from document_platform.domain.processing import InvoiceProposalGenerationFailureCode


class ProposeInvoiceFieldsActivity:
    def __init__(
        self,
        propose_invoice_fields: ProposeInvoiceFieldsHandler,
        *,
        enabled: bool = True,
        max_concurrent_requests: int = 1,
    ) -> None:
        if max_concurrent_requests < 1:
            raise ValueError("max_concurrent_requests must be positive")
        self._propose_invoice_fields = propose_invoice_fields
        self._enabled = enabled
        self._request_slots = asyncio.Semaphore(max_concurrent_requests)

    @activity.defn(name=PROPOSE_INVOICE_FIELDS_ACTIVITY)
    async def propose_invoice_fields(self, processing_run_id: str) -> None:
        if not self._enabled:
            return
        try:
            async with self._request_slots:
                await self._propose_invoice_fields(ProposeInvoiceFields(UUID(processing_run_id)))
        except InvoiceProposalGenerationFailed as error:
            raise ApplicationError(
                "invoice proposal provider failed",
                type=f"{INVOICE_PROPOSAL_FAILURE_TYPE_PREFIX}{error.code.value}",
                non_retryable=error.code is InvoiceProposalGenerationFailureCode.INVALID_RESPONSE,
            ) from None
