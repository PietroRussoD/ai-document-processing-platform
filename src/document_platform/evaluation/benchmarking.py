"""Small measurement helpers for local evaluation experiments."""

from collections.abc import Callable
from dataclasses import dataclass
from math import ceil
from statistics import fmean
from time import perf_counter_ns

from document_platform.evaluation.invoice_extraction import InvoiceFields


@dataclass(frozen=True, slots=True)
class LatencySummary:
    request_count: int
    total_milliseconds: float
    minimum_milliseconds: float
    mean_milliseconds: float
    p95_milliseconds: float
    maximum_milliseconds: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "request_count": self.request_count,
            "total_milliseconds": self.total_milliseconds,
            "minimum_milliseconds": self.minimum_milliseconds,
            "mean_milliseconds": self.mean_milliseconds,
            "p95_milliseconds": self.p95_milliseconds,
            "maximum_milliseconds": self.maximum_milliseconds,
        }


class TimedInvoiceExtractor:
    """Measure completed extraction calls without changing their behavior."""

    def __init__(self, extractor: Callable[[str], InvoiceFields]) -> None:
        self._extractor = extractor
        self._elapsed_nanoseconds: list[int] = []

    def extract(self, text: str) -> InvoiceFields:
        started_at = perf_counter_ns()
        try:
            return self._extractor(text)
        finally:
            self._elapsed_nanoseconds.append(perf_counter_ns() - started_at)

    def latency_summary(self) -> LatencySummary:
        return summarize_latencies(self._elapsed_nanoseconds)


def summarize_latencies(elapsed_nanoseconds: list[int]) -> LatencySummary:
    if not elapsed_nanoseconds:
        raise ValueError("at least one elapsed duration is required")
    if any(duration < 0 for duration in elapsed_nanoseconds):
        raise ValueError("elapsed durations must not be negative")
    elapsed_milliseconds = [duration / 1_000_000 for duration in elapsed_nanoseconds]
    sorted_milliseconds = sorted(elapsed_milliseconds)
    p95_index = ceil(0.95 * len(sorted_milliseconds)) - 1
    return LatencySummary(
        request_count=len(elapsed_milliseconds),
        total_milliseconds=round(sum(elapsed_milliseconds), 3),
        minimum_milliseconds=round(sorted_milliseconds[0], 3),
        mean_milliseconds=round(fmean(elapsed_milliseconds), 3),
        p95_milliseconds=round(sorted_milliseconds[p95_index], 3),
        maximum_milliseconds=round(sorted_milliseconds[-1], 3),
    )
