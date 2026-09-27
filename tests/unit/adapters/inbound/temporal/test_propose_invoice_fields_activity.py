"""Temporal advisory invoice proposal activity tests."""

from uuid import UUID

import pytest

from document_platform.adapters.inbound.temporal import ProposeInvoiceFieldsActivity
from document_platform.application.commands import ProposeInvoiceFields

RUN_ID = UUID("a7a7a7a7-a7a7-47a7-87a7-a7a7a7a7a7a7")


class RecordingProposeInvoiceFields:
    def __init__(self) -> None:
        self.commands: list[ProposeInvoiceFields] = []

    async def __call__(self, command: ProposeInvoiceFields) -> None:
        self.commands.append(command)


@pytest.mark.anyio
async def test_maps_run_id_without_returning_proposal_to_temporal() -> None:
    handler = RecordingProposeInvoiceFields()
    activity = ProposeInvoiceFieldsActivity(handler)  # type: ignore[arg-type]

    result = await activity.propose_invoice_fields(str(RUN_ID))

    assert handler.commands == [ProposeInvoiceFields(RUN_ID)]
    assert result is None
