"""Temporal invoice-validation application activity tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from document_platform.adapters.inbound.temporal import ApplyInvoiceValidationActivity
from document_platform.application.commands import ApplyInvoiceValidation, InvoiceValidationApplied
from document_platform.domain.processing import InvoiceValidationDecision

RUN_ID = UUID("f2f2f2f2-f2f2-42f2-82f2-f2f2f2f2f2f2")


class RecordingApplyInvoiceValidation:
    def __init__(self) -> None:
        self.commands: list[ApplyInvoiceValidation] = []

    async def __call__(self, command: ApplyInvoiceValidation) -> InvoiceValidationApplied:
        self.commands.append(command)
        return InvoiceValidationApplied(
            command.processing_run_id,
            InvoiceValidationDecision.AUTO_APPROVE,
            datetime(2026, 9, 17, tzinfo=UTC),
            False,
        )


@pytest.mark.anyio
async def test_maps_the_temporal_argument_to_the_application_command() -> None:
    handler = RecordingApplyInvoiceValidation()
    activity = ApplyInvoiceValidationActivity(handler)  # type: ignore[arg-type]

    await activity.apply_invoice_validation(str(RUN_ID))

    assert handler.commands == [ApplyInvoiceValidation(RUN_ID)]
