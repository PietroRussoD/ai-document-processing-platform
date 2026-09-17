"""Temporal activity for deterministic structured invoice extraction."""

from uuid import UUID

from temporalio import activity

from document_platform.application.commands import ExtractInvoice, ExtractInvoiceHandler
from document_platform.application.temporal_contracts import EXTRACT_INVOICE_ACTIVITY


class ExtractInvoiceActivity:
    def __init__(self, extract_invoice: ExtractInvoiceHandler) -> None:
        self._extract_invoice = extract_invoice

    @activity.defn(name=EXTRACT_INVOICE_ACTIVITY)
    async def extract_invoice(self, processing_run_id: str) -> None:
        await self._extract_invoice(ExtractInvoice(UUID(processing_run_id)))
