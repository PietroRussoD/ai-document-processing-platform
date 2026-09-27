"""Terminal AI provider failure contract tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from document_platform.domain.processing import (
    AiInvoiceProposalFailure,
    InvalidAiInvoiceProposalFailure,
    InvoiceModelProvider,
    InvoiceProposalGenerationFailureCode,
)


def failure(**overrides: object) -> AiInvoiceProposalFailure:
    values = {
        "processing_run_id": UUID(int=1),
        "provider": InvoiceModelProvider.OLLAMA,
        "model_reference": "qwen3:8b",
        "code": InvoiceProposalGenerationFailureCode.TIMEOUT,
        "failed_at": datetime(2026, 9, 27, tzinfo=UTC),
        **overrides,
    }
    return AiInvoiceProposalFailure(**values)  # type: ignore[arg-type]


def test_records_only_safe_failure_metadata() -> None:
    result = failure()

    assert result.code is InvoiceProposalGenerationFailureCode.TIMEOUT
    assert not hasattr(result, "raw_error")


@pytest.mark.parametrize(
    "overrides",
    [
        {"processing_run_id": UUID(int=0)},
        {"model_reference": " "},
        {"code": "PRIVATE_SERVER_ERROR"},
        {"failed_at": datetime(2026, 9, 27)},
    ],
)
def test_rejects_invalid_failure_metadata(overrides: dict[str, object]) -> None:
    with pytest.raises(InvalidAiInvoiceProposalFailure):
        failure(**overrides)
