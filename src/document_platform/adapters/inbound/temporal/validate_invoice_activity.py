"""Temporal activity for deterministic invoice validation."""

from uuid import UUID

from temporalio import activity

from document_platform.application.commands import ValidateInvoice, ValidateInvoiceHandler
from document_platform.application.temporal_contracts import VALIDATE_INVOICE_ACTIVITY


class ValidateInvoiceActivity:
    def __init__(self, validate_invoice: ValidateInvoiceHandler) -> None:
        self._validate_invoice = validate_invoice

    @activity.defn(name=VALIDATE_INVOICE_ACTIVITY)
    async def validate_invoice(self, processing_run_id: str) -> None:
        await self._validate_invoice(ValidateInvoice(UUID(processing_run_id)))
