"""Regression checks for the versioned synthetic invoice corpus."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from document_platform.domain.processing import DeterministicInvoiceExtractionPolicy
from document_platform.evaluation import EvaluationCase, load_invoice_extraction_corpus

CORPUS_PATH = Path(__file__).resolve().parents[3] / "docs/evaluation/invoice-extraction-v1.json"
EXTRACTED_AT = datetime(2026, 9, 19, 8, 0, tzinfo=UTC)
RUN_ID = UUID("e4e4e4e4-e4e4-44e4-84e4-e4e4e4e4e4e4")


CORPUS = load_invoice_extraction_corpus(CORPUS_PATH)


@pytest.mark.parametrize("case", CORPUS.cases, ids=lambda case: case.id)
def test_deterministic_policy_matches_the_versioned_corpus(case: EvaluationCase) -> None:
    extraction = DeterministicInvoiceExtractionPolicy().extract(
        processing_run_id=RUN_ID,
        text=case.text,
        extracted_at=EXTRACTED_AT,
    )

    assert {
        "invoice_number": extraction.invoice_number,
        "issue_date": extraction.issue_date.isoformat() if extraction.issue_date else None,
        "supplier_name": extraction.supplier_name,
        "currency": extraction.currency,
        "total_amount": str(extraction.total_amount) if extraction.total_amount else None,
    } == case.expected.as_dict()
