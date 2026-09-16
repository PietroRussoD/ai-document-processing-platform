"""Deterministic business-document classification tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from document_platform.domain.processing import (
    BusinessDocumentType,
    DocumentClassification,
    DocumentClassificationPolicy,
    DocumentClassificationReason,
    InvalidDocumentClassification,
)

AT = datetime(2026, 9, 16, 11, 0, tzinfo=UTC)
RUN_ID = UUID("a1a1a1a1-a1a1-41a1-81a1-a1a1a1a1a1a1")


def classify(text: str):
    return DocumentClassificationPolicy().classify(
        processing_run_id=RUN_ID,
        text=text,
        classified_at=AT,
    )


def test_classifies_a_single_keyword_match_case_insensitively() -> None:
    result = classify("FATTURA numero 42")

    assert result.document_type is BusinessDocumentType.INVOICE
    assert result.reason is DocumentClassificationReason.KEYWORD_MATCHED


def test_does_not_match_a_keyword_inside_a_larger_word() -> None:
    result = classify("The invoiced amount is 42")

    assert result.document_type is BusinessDocumentType.UNKNOWN
    assert result.reason is DocumentClassificationReason.NO_MATCH


def test_marks_multiple_document_types_as_ambiguous() -> None:
    result = classify("Invoice issued after credit note")

    assert result.document_type is BusinessDocumentType.UNKNOWN
    assert result.reason is DocumentClassificationReason.AMBIGUOUS_MATCH


@pytest.mark.parametrize(
    ("processing_run_id", "classified_at", "document_type", "reason"),
    [
        (
            UUID(int=0),
            AT,
            BusinessDocumentType.UNKNOWN,
            DocumentClassificationReason.NO_MATCH,
        ),
        (
            RUN_ID,
            datetime(2026, 9, 16, 11, 0),
            BusinessDocumentType.UNKNOWN,
            DocumentClassificationReason.NO_MATCH,
        ),
        (
            RUN_ID,
            AT,
            BusinessDocumentType.INVOICE,
            DocumentClassificationReason.NO_MATCH,
        ),
    ],
)
def test_rejects_invalid_classification_invariants(
    processing_run_id: UUID,
    classified_at: datetime,
    document_type: BusinessDocumentType,
    reason: DocumentClassificationReason,
) -> None:
    with pytest.raises(InvalidDocumentClassification):
        DocumentClassification(
            processing_run_id=processing_run_id,
            document_type=document_type,
            reason=reason,
            classified_at=classified_at,
        )
