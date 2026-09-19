"""Evaluate the deterministic invoice extractor against the versioned corpus."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from document_platform.domain.processing import DeterministicInvoiceExtractionPolicy
from document_platform.evaluation import (
    InvoiceExtractionEvaluator,
    InvoiceFields,
    load_invoice_extraction_corpus,
)

CORPUS_PATH = Path(__file__).resolve().parents[1] / "docs/evaluation/invoice-extraction-v1.json"
EVALUATION_RUN_ID = UUID("f5f5f5f5-f5f5-45f5-85f5-f5f5f5f5f5f5")
EVALUATED_AT = datetime(2026, 9, 19, 8, 0, tzinfo=UTC)


def main() -> None:
    corpus = load_invoice_extraction_corpus(CORPUS_PATH)
    report = InvoiceExtractionEvaluator().evaluate(
        corpus=corpus,
        extractor=_extract_deterministically,
    )
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))


def _extract_deterministically(text: str) -> InvoiceFields:
    extraction = DeterministicInvoiceExtractionPolicy().extract(
        processing_run_id=EVALUATION_RUN_ID,
        text=text,
        extracted_at=EVALUATED_AT,
    )
    return InvoiceFields(
        invoice_number=extraction.invoice_number,
        issue_date=extraction.issue_date.isoformat() if extraction.issue_date else None,
        supplier_name=extraction.supplier_name,
        currency=extraction.currency,
        total_amount=str(extraction.total_amount) if extraction.total_amount else None,
    )


if __name__ == "__main__":
    main()
