"""Temporal activity for applying an invoice-validation decision."""

from uuid import UUID

from temporalio import activity

from document_platform.application.commands import (
    ApplyInvoiceValidation,
    ApplyInvoiceValidationHandler,
)
from document_platform.application.temporal_contracts import APPLY_INVOICE_VALIDATION_ACTIVITY


class ApplyInvoiceValidationActivity:
    def __init__(self, apply_invoice_validation: ApplyInvoiceValidationHandler) -> None:
        self._apply_invoice_validation = apply_invoice_validation

    @activity.defn(name=APPLY_INVOICE_VALIDATION_ACTIVITY)
    async def apply_invoice_validation(self, processing_run_id: str) -> None:
        await self._apply_invoice_validation(ApplyInvoiceValidation(UUID(processing_run_id)))
