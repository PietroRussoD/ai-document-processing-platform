"""Temporal invoice-validation activity tests."""

from uuid import UUID

import pytest

from document_platform.adapters.inbound.temporal import ValidateInvoiceActivity
from document_platform.application.commands import InvoiceValidated, ValidateInvoice
from document_platform.domain.processing import InvoiceValidationDecision

RUN_ID = UUID("f1f1f1f1-f1f1-41f1-81f1-f1f1f1f1f1f1")


class RecordingValidateInvoice:
    def __init__(self) -> None:
        self.commands: list[ValidateInvoice] = []

    async def __call__(self, command: ValidateInvoice) -> InvoiceValidated:
        self.commands.append(command)
        return InvoiceValidated(
            command.processing_run_id,
            InvoiceValidationDecision.AUTO_APPROVE,
            False,
        )


@pytest.mark.anyio
async def test_maps_the_temporal_argument_to_the_application_command() -> None:
    handler = RecordingValidateInvoice()
    activity = ValidateInvoiceActivity(handler)  # type: ignore[arg-type]

    await activity.validate_invoice(str(RUN_ID))

    assert handler.commands == [ValidateInvoice(RUN_ID)]
