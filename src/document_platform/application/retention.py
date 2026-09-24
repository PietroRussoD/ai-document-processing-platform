"""Shared policy and result types for document retention use cases."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from document_platform.application.ports import DocumentRetentionSnapshot


class InvalidRetentionPeriod(ValueError):
    """Raised when a retention period or clock value is invalid."""


@dataclass(frozen=True, slots=True)
class DocumentRetentionReport:
    retention_days: int
    cutoff: datetime
    snapshot: DocumentRetentionSnapshot


def calculate_retention_cutoff(*, retention_days: int, now: datetime) -> datetime:
    if retention_days < 1:
        raise InvalidRetentionPeriod("retention_days must be positive")
    if now.tzinfo is None or now.utcoffset() is None:
        raise InvalidRetentionPeriod("clock must return a timezone-aware datetime")
    return now - timedelta(days=retention_days)
