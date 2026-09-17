"""Temporal invoice-extraction activity tests."""

from uuid import UUID

import pytest

from document_platform.adapters.inbound.temporal import ExtractInvoiceActivity
from document_platform.application.commands import ExtractInvoice, InvoiceExtracted

RUN_ID = UUID("a7a7a7a7-a7a7-47a7-87a7-a7a7a7a7a7a7")


class RecordingExtractInvoice:
    def __init__(self) -> None:
        self.commands: list[ExtractInvoice] = []

    async def __call__(self, command: ExtractInvoice) -> InvoiceExtracted:
        self.commands.append(command)
        return InvoiceExtracted(command.processing_run_id, replayed=False)


@pytest.mark.anyio
async def test_maps_the_temporal_argument_to_the_application_command() -> None:
    handler = RecordingExtractInvoice()
    activity = ExtractInvoiceActivity(handler)  # type: ignore[arg-type]

    await activity.extract_invoice(str(RUN_ID))

    assert handler.commands == [ExtractInvoice(RUN_ID)]
