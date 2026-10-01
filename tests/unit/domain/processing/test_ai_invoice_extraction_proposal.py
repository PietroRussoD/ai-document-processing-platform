"""AI invoice proposal domain-contract tests."""

from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from document_platform.domain.processing import (
    AiInvoiceExtractionProposal,
    InvalidInvoiceExtractionProposal,
    InvoiceModelProvider,
    InvoiceProposalField,
    InvoiceProposalIssue,
    InvoiceProposalIssueCode,
    InvoiceProposalStatus,
)

AT = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
RUN_ID = UUID("e5e5e5e5-e5e5-45e5-85e5-e5e5e5e5e5e5")
TEXT_HASH = "a" * 64


def proposal(**overrides: object) -> AiInvoiceExtractionProposal:
    values: dict[str, object] = {
        "processing_run_id": RUN_ID,
        "schema_version": 1,
        "provider": InvoiceModelProvider.OLLAMA,
        "model_reference": "qwen3:8b",
        "model_digest": "sha256:" + "b" * 64,
        "prompt_version": "invoice-fields-v1",
        "selected_text_sha256": TEXT_HASH,
        "status": InvoiceProposalStatus.VALID,
        "invoice_number": "INV-42",
        "issue_date": date(2026, 9, 27),
        "supplier_name": "Example Supplier Ltd",
        "currency": "EUR",
        "total_amount": Decimal("125.50"),
        "issues": (),
        "proposed_at": AT,
    }
    values.update(overrides)
    return AiInvoiceExtractionProposal(**values)  # type: ignore[arg-type]


def test_accepts_a_complete_proposal_with_model_and_input_provenance() -> None:
    result = proposal()

    assert result.status is InvoiceProposalStatus.VALID
    assert result.provider is InvoiceModelProvider.OLLAMA
    assert result.model_reference == "qwen3:8b"
    assert result.selected_text_sha256 == TEXT_HASH
    assert result.total_amount == Decimal("125.50")


def test_accepts_a_partial_proposal_with_field_level_issue() -> None:
    issue = InvoiceProposalIssue(
        code=InvoiceProposalIssueCode.MISSING_FIELD,
        field=InvoiceProposalField.ISSUE_DATE,
    )

    result = proposal(
        status=InvoiceProposalStatus.PARTIAL,
        issue_date=None,
        issues=(issue,),
    )

    assert result.issue_date is None
    assert result.issues == (issue,)


def test_accepts_an_invalid_response_without_proposed_values() -> None:
    issue = InvoiceProposalIssue(
        code=InvoiceProposalIssueCode.MALFORMED_RESPONSE,
        field=None,
    )

    result = proposal(
        status=InvoiceProposalStatus.INVALID,
        invoice_number=None,
        issue_date=None,
        supplier_name=None,
        currency=None,
        total_amount=None,
        issues=(issue,),
    )

    assert result.status is InvoiceProposalStatus.INVALID
    assert result.issues == (issue,)


@pytest.mark.parametrize(
    "overrides",
    [
        {"schema_version": 2},
        {"schema_version": True},
        {"selected_text_sha256": "not-a-hash"},
        {"model_digest": "not-a-digest"},
        {"currency": "eur"},
        {"currency": "ZZZ"},
        {"total_amount": Decimal("-1.00")},
        {"total_amount": Decimal("1.12345")},
        {"proposed_at": datetime(2026, 9, 27, 12, 0)},
        {"status": InvoiceProposalStatus.PARTIAL},
        {
            "status": InvoiceProposalStatus.VALID,
            "issues": (
                InvoiceProposalIssue(
                    InvoiceProposalIssueCode.INVALID_FIELD_VALUE, InvoiceProposalField.TOTAL_AMOUNT
                ),
            ),
        },
    ],
)
def test_rejects_invalid_proposal_contract(overrides: dict[str, object]) -> None:
    with pytest.raises(InvalidInvoiceExtractionProposal):
        proposal(**overrides)


@pytest.mark.parametrize(
    ("code", "field"),
    [
        (InvoiceProposalIssueCode.MALFORMED_RESPONSE, InvoiceProposalField.INVOICE_NUMBER),
        (InvoiceProposalIssueCode.MISSING_FIELD, None),
    ],
)
def test_rejects_issue_field_inconsistent_with_issue_code(
    code: InvoiceProposalIssueCode,
    field: InvoiceProposalField | None,
) -> None:
    with pytest.raises(InvalidInvoiceExtractionProposal):
        InvoiceProposalIssue(code=code, field=field)


def test_proposal_is_immutable() -> None:
    result = proposal()

    with pytest.raises(FrozenInstanceError):
        result.invoice_number = "CHANGED"  # type: ignore[misc]
