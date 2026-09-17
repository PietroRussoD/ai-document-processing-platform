"""Deterministic invoice-validation policy tests."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from document_platform.domain.processing import (
    InvalidInvoiceValidation,
    InvoiceExtraction,
    InvoiceExtractionMethod,
    InvoiceValidation,
    InvoiceValidationDecision,
    InvoiceValidationIssue,
    InvoiceValidationPolicy,
)

AT = datetime(2026, 9, 17, 9, 0, tzinfo=UTC)
RUN_ID = UUID("a8a8a8a8-a8a8-48a8-88a8-a8a8a8a8a8a8")


def extraction(**overrides: object) -> InvoiceExtraction:
    values: dict[str, object] = {
        "processing_run_id": RUN_ID,
        "method": InvoiceExtractionMethod.DETERMINISTIC_RULES,
        "invoice_number": "INV-42",
        "issue_date": date(2026, 9, 17),
        "supplier_name": "Acme Ltd",
        "currency": "EUR",
        "total_amount": Decimal("12.50"),
        "extracted_at": AT,
    }
    values.update(overrides)
    return InvoiceExtraction(**values)  # type: ignore[arg-type]


def test_auto_approves_a_complete_invoice_with_a_positive_total() -> None:
    result = InvoiceValidationPolicy().validate(extraction=extraction(), validated_at=AT)

    assert result.decision is InvoiceValidationDecision.AUTO_APPROVE
    assert result.issues == ()


def test_requires_review_for_each_missing_or_invalid_critical_field() -> None:
    result = InvoiceValidationPolicy().validate(
        extraction=extraction(
            invoice_number=None,
            issue_date=None,
            supplier_name=None,
            currency=None,
            total_amount=Decimal("0"),
        ),
        validated_at=AT,
    )

    assert result.decision is InvoiceValidationDecision.REVIEW_REQUIRED
    assert result.issues == (
        InvoiceValidationIssue.MISSING_INVOICE_NUMBER,
        InvoiceValidationIssue.MISSING_ISSUE_DATE,
        InvoiceValidationIssue.MISSING_SUPPLIER_NAME,
        InvoiceValidationIssue.MISSING_CURRENCY,
        InvoiceValidationIssue.NON_POSITIVE_TOTAL_AMOUNT,
    )


@pytest.mark.parametrize(
    ("decision", "issues", "validated_at"),
    [
        (InvoiceValidationDecision.AUTO_APPROVE, (InvoiceValidationIssue.MISSING_CURRENCY,), AT),
        (InvoiceValidationDecision.REVIEW_REQUIRED, (), AT),
        (
            InvoiceValidationDecision.REVIEW_REQUIRED,
            (
                InvoiceValidationIssue.MISSING_CURRENCY,
                InvoiceValidationIssue.MISSING_CURRENCY,
            ),
            AT,
        ),
        (InvoiceValidationDecision.AUTO_APPROVE, (), datetime(2026, 9, 17, 9, 0)),
    ],
)
def test_rejects_invalid_validation_invariants(
    decision: InvoiceValidationDecision,
    issues: tuple[InvoiceValidationIssue, ...],
    validated_at: datetime,
) -> None:
    with pytest.raises(InvalidInvoiceValidation):
        InvoiceValidation(
            processing_run_id=RUN_ID,
            decision=decision,
            issues=issues,
            validated_at=validated_at,
        )
