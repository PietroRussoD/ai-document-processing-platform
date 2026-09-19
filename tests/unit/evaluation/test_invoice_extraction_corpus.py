"""Regression checks for the versioned synthetic invoice corpus."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest

from document_platform.domain.processing import DeterministicInvoiceExtractionPolicy

CORPUS_PATH = Path(__file__).resolve().parents[3] / "docs/evaluation/invoice-extraction-v1.json"
EXTRACTED_AT = datetime(2026, 9, 19, 8, 0, tzinfo=UTC)
RUN_ID = UUID("e4e4e4e4-e4e4-44e4-84e4-e4e4e4e4e4e4")


def _load_cases() -> list[dict[str, Any]]:
    corpus = cast(dict[str, Any], json.loads(CORPUS_PATH.read_text(encoding="utf-8")))
    assert corpus["dataset_id"] == "invoice-extraction-v1"
    assert corpus["schema_version"] == 1
    return cast(list[dict[str, Any]], corpus["cases"])


@pytest.mark.parametrize("case", _load_cases(), ids=lambda case: str(case["id"]))
def test_deterministic_policy_matches_the_versioned_corpus(case: dict[str, Any]) -> None:
    extraction = DeterministicInvoiceExtractionPolicy().extract(
        processing_run_id=RUN_ID,
        text=cast(str, case["text"]),
        extracted_at=EXTRACTED_AT,
    )

    assert {
        "invoice_number": extraction.invoice_number,
        "issue_date": extraction.issue_date.isoformat() if extraction.issue_date else None,
        "supplier_name": extraction.supplier_name,
        "currency": extraction.currency,
        "total_amount": str(extraction.total_amount) if extraction.total_amount else None,
    } == case["expected"]
