"""Invoice-extraction evaluator tests."""

import json
from pathlib import Path

import pytest

from document_platform.evaluation import (
    EvaluationCase,
    EvaluationCorpus,
    InvalidEvaluationCorpus,
    InvoiceExtractionEvaluator,
    InvoiceFields,
    load_invoice_extraction_corpus,
)


def test_reports_per_field_and_exact_case_matches() -> None:
    corpus = EvaluationCorpus(
        dataset_id="test-corpus",
        schema_version=1,
        cases=(
            EvaluationCase(
                id="matching-case",
                text="matching",
                expected=fields(invoice_number="INV-1", total_amount="10.00"),
            ),
            EvaluationCase(
                id="mismatching-case",
                text="mismatching",
                expected=fields(invoice_number="INV-2", total_amount="20.00"),
            ),
        ),
    )

    report = InvoiceExtractionEvaluator().evaluate(corpus=corpus, extractor=extract)

    assert report.exact_case_matches == 1
    assert report.total_cases == 2
    assert {score.field: score.exact_matches for score in report.field_evaluations} == {
        "invoice_number": 1,
        "issue_date": 2,
        "supplier_name": 2,
        "currency": 2,
        "total_amount": 1,
    }
    assert report.mismatches[0].case_id == "mismatching-case"
    assert report.mismatches[0].field == "invoice_number"
    assert report.as_dict()["exact_case_match_rate"] == 0.5


def test_records_each_mismatched_field_for_an_incomplete_prediction() -> None:
    corpus = EvaluationCorpus(
        dataset_id="test-corpus",
        schema_version=1,
        cases=(
            EvaluationCase(
                id="missing-fields",
                text="missing",
                expected=fields(invoice_number="INV-3", currency="EUR"),
            ),
        ),
    )

    report = InvoiceExtractionEvaluator().evaluate(
        corpus=corpus,
        extractor=lambda _text: fields(),
    )

    assert report.exact_case_matches == 0
    mismatch_values = [
        (mismatch.field, mismatch.expected, mismatch.actual) for mismatch in report.mismatches
    ]
    assert mismatch_values == [
        ("invoice_number", "INV-3", None),
        ("currency", "EUR", None),
    ]


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], "corpus must be an object"),
        (
            {"dataset_id": "test", "schema_version": 1, "cases": []},
            "cases must be a non-empty array",
        ),
        (
            {
                "dataset_id": "test",
                "schema_version": 1,
                "cases": [
                    {
                        "id": "case-1",
                        "text": "text",
                        "expected": {"invoice_number": "INV-1"},
                    }
                ],
            },
            "case.expected must contain exactly the invoice fields",
        ),
    ],
)
def test_rejects_an_invalid_corpus(tmp_path: Path, payload: object, message: str) -> None:
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(InvalidEvaluationCorpus, match=message):
        load_invoice_extraction_corpus(path)


def extract(text: str) -> InvoiceFields:
    return fields(invoice_number="INV-1", total_amount="10.00") if text == "matching" else fields()


def fields(
    *,
    invoice_number: str | None = None,
    issue_date: str | None = None,
    supplier_name: str | None = None,
    currency: str | None = None,
    total_amount: str | None = None,
) -> InvoiceFields:
    return InvoiceFields(
        invoice_number=invoice_number,
        issue_date=issue_date,
        supplier_name=supplier_name,
        currency=currency,
        total_amount=total_amount,
    )
