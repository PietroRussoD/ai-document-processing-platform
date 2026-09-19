"""Tests for local evaluation measurement helpers."""

import pytest

from document_platform.evaluation import InvoiceFields, TimedInvoiceExtractor, summarize_latencies


def test_summarizes_latencies_using_nearest_rank_p95() -> None:
    summary = summarize_latencies([1_000_000, 2_000_000, 3_000_000, 4_000_000])

    assert summary.as_dict() == {
        "request_count": 4,
        "total_milliseconds": 10.0,
        "minimum_milliseconds": 1.0,
        "mean_milliseconds": 2.5,
        "p95_milliseconds": 4.0,
        "maximum_milliseconds": 4.0,
    }


def test_measures_a_successful_extraction_call() -> None:
    expected = InvoiceFields(
        invoice_number="INV-1",
        issue_date=None,
        supplier_name=None,
        currency=None,
        total_amount=None,
    )
    extractor = TimedInvoiceExtractor(lambda _text: expected)

    assert extractor.extract("invoice text") == expected

    summary = extractor.latency_summary()
    assert summary.request_count == 1
    assert summary.minimum_milliseconds >= 0


def test_records_latency_when_an_extraction_call_fails() -> None:
    def fail(_text: str) -> InvoiceFields:
        raise RuntimeError("model unavailable")

    extractor = TimedInvoiceExtractor(fail)

    with pytest.raises(RuntimeError, match="model unavailable"):
        extractor.extract("invoice text")

    assert extractor.latency_summary().request_count == 1


@pytest.mark.parametrize(
    ("elapsed_nanoseconds", "message"),
    [([], "at least one"), ([-1], "must not be negative")],
)
def test_rejects_invalid_latency_samples(elapsed_nanoseconds: list[int], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        summarize_latencies(elapsed_nanoseconds)
