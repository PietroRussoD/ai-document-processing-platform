"""Invoice review-correction domain-contract tests."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from document_platform.domain.processing import (
    InvalidInvoiceReviewCorrection,
    InvoiceReviewCorrection,
    InvoiceReviewField,
    InvoiceReviewFieldCorrection,
)

RUN_ID = UUID("c8c8c8c8-c8c8-48c8-88c8-c8c8c8c8c8c8")
AT = datetime(2026, 9, 18, 20, 0, tzinfo=UTC)


def correction(**overrides: object) -> InvoiceReviewCorrection:
    values: dict[str, object] = {
        "processing_run_id": RUN_ID,
        "corrections": (
            InvoiceReviewFieldCorrection(
                field=InvoiceReviewField.ISSUE_DATE,
                corrected_value=date(2026, 9, 18),
            ),
        ),
        "corrected_at": AT,
    }
    values.update(overrides)
    return InvoiceReviewCorrection(**values)  # type: ignore[arg-type]


def test_accepts_a_typed_immutable_correction_set() -> None:
    result = correction(
        corrections=(
            InvoiceReviewFieldCorrection(
                field=InvoiceReviewField.ISSUE_DATE,
                corrected_value=date(2026, 9, 18),
            ),
            InvoiceReviewFieldCorrection(
                field=InvoiceReviewField.TOTAL_AMOUNT,
                corrected_value=Decimal("39.98"),
            ),
        )
    )

    assert tuple(item.field for item in result.corrections) == (
        InvoiceReviewField.ISSUE_DATE,
        InvoiceReviewField.TOTAL_AMOUNT,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (InvoiceReviewField.INVOICE_NUMBER, "   "),
        (InvoiceReviewField.ISSUE_DATE, datetime(2026, 9, 18, tzinfo=UTC)),
        (InvoiceReviewField.SUPPLIER_NAME, ""),
        (InvoiceReviewField.CURRENCY, "eur"),
        (InvoiceReviewField.TOTAL_AMOUNT, Decimal("0")),
        (InvoiceReviewField.TOTAL_AMOUNT, Decimal("39.12345")),
    ],
)
def test_rejects_invalid_corrected_field_values(
    field: InvoiceReviewField,
    value: object,
) -> None:
    with pytest.raises(InvalidInvoiceReviewCorrection):
        InvoiceReviewFieldCorrection(
            field=field,
            corrected_value=value,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("processing_run_id", "corrections", "corrected_at"),
    [
        (UUID(int=0), (), AT),
        (RUN_ID, (), AT),
        (RUN_ID, [], AT),
        (
            RUN_ID,
            (
                InvoiceReviewFieldCorrection(
                    field=InvoiceReviewField.ISSUE_DATE,
                    corrected_value=date(2026, 9, 18),
                ),
                InvoiceReviewFieldCorrection(
                    field=InvoiceReviewField.ISSUE_DATE,
                    corrected_value=date(2026, 9, 19),
                ),
            ),
            AT,
        ),
        (RUN_ID, (), datetime(2026, 9, 18, 20, 0)),
    ],
)
def test_rejects_invalid_correction_set_invariants(
    processing_run_id: UUID,
    corrections: object,
    corrected_at: datetime,
) -> None:
    with pytest.raises(InvalidInvoiceReviewCorrection):
        correction(
            processing_run_id=processing_run_id,
            corrections=corrections,
            corrected_at=corrected_at,
        )
