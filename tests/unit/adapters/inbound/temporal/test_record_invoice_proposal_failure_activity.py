"""Temporal terminal AI failure activity tests."""

from uuid import UUID

import pytest

from document_platform.adapters.inbound.temporal import RecordInvoiceProposalFailureActivity
from document_platform.application.commands import RecordInvoiceProposalFailure
from document_platform.domain.processing import (
    InvoiceModelProvider,
    InvoiceProposalGenerationFailureCode,
)

RUN_ID = UUID("d7d7d7d7-d7d7-47d7-87d7-d7d7d7d7d7d7")


class RecordingFailureHandler:
    def __init__(self) -> None:
        self.commands: list[RecordInvoiceProposalFailure] = []

    async def __call__(self, command: RecordInvoiceProposalFailure) -> None:
        self.commands.append(command)


@pytest.mark.anyio
async def test_maps_only_safe_code_and_run_id_without_returning_data_to_history() -> None:
    recorder = RecordingFailureHandler()
    activity = RecordInvoiceProposalFailureActivity(
        recorder,  # type: ignore[arg-type]
        provider=InvoiceModelProvider.OLLAMA,
        model_reference="qwen3:8b",
    )

    result = await activity.record_invoice_proposal_failure(str(RUN_ID), "TIMEOUT")

    assert recorder.commands == [
        RecordInvoiceProposalFailure(
            processing_run_id=RUN_ID,
            provider=InvoiceModelProvider.OLLAMA,
            model_reference="qwen3:8b",
            code=InvoiceProposalGenerationFailureCode.TIMEOUT,
        )
    ]
    assert result is None


@pytest.mark.anyio
async def test_rejects_unknown_failure_code() -> None:
    recorder = RecordingFailureHandler()
    activity = RecordInvoiceProposalFailureActivity(
        recorder,  # type: ignore[arg-type]
        provider=InvoiceModelProvider.OLLAMA,
        model_reference="qwen3:8b",
    )

    with pytest.raises(ValueError):
        await activity.record_invoice_proposal_failure(str(RUN_ID), "PRIVATE_PROVIDER_ERROR")

    assert recorder.commands == []
