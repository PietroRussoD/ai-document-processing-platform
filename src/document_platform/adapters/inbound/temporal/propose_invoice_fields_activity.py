"""Temporal activity for advisory invoice field proposals."""

from uuid import UUID

from temporalio import activity

from document_platform.application.commands import ProposeInvoiceFields, ProposeInvoiceFieldsHandler
from document_platform.application.temporal_contracts import PROPOSE_INVOICE_FIELDS_ACTIVITY


class ProposeInvoiceFieldsActivity:
    def __init__(self, propose_invoice_fields: ProposeInvoiceFieldsHandler) -> None:
        self._propose_invoice_fields = propose_invoice_fields

    @activity.defn(name=PROPOSE_INVOICE_FIELDS_ACTIVITY)
    async def propose_invoice_fields(self, processing_run_id: str) -> None:
        await self._propose_invoice_fields(ProposeInvoiceFields(UUID(processing_run_id)))
