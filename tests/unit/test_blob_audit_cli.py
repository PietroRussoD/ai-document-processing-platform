"""Argument validation for the report-only blob audit command."""

import json
import sys
from datetime import UTC, datetime

import pytest

from document_platform import blob_audit


def test_prints_aggregate_report_without_blob_keys(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    report = blob_audit.BlobAuditReport(
        older_than=datetime(2026, 9, 23, 12, 0, tzinfo=UTC),
        scan_limit=50,
        scanned_entries=3,
        scan_truncated=False,
        published_blobs=2,
        recent_blobs=1,
        checked_old_blobs=1,
        potential_orphans=1,
        potential_orphan_bytes=123,
        temporary_uploads=0,
        incoming_uploads=0,
        old_temporary_uploads=0,
        old_incoming_uploads=0,
        recent_staged_uploads=0,
        old_staged_upload_bytes=0,
        unrecognized_entries=0,
    )

    async def fake_summary(
        *, settings: object, now: datetime, min_age_hours: int, scan_limit: int
    ) -> blob_audit.BlobAuditReport:
        assert now.tzinfo is not None
        assert min_age_hours == 48
        assert scan_limit == 50
        return report

    monkeypatch.setattr(blob_audit, "Settings", lambda: object())
    monkeypatch.setattr(blob_audit, "summarize_blob_candidates", fake_summary)
    monkeypatch.setattr(sys, "argv", ["blob_audit", "--min-age-hours", "48", "--scan-limit", "50"])

    blob_audit.main()

    assert json.loads(capsys.readouterr().out) == {
        "mode": "report-only",
        "older_than": "2026-09-23T12:00:00+00:00",
        "scan_limit": 50,
        "scanned_entries": 3,
        "scan_truncated": False,
        "published_blobs": 2,
        "recent_blobs": 1,
        "checked_old_blobs": 1,
        "potential_orphans": 1,
        "potential_orphan_bytes": 123,
        "temporary_uploads": 0,
        "incoming_uploads": 0,
        "old_temporary_uploads": 0,
        "old_incoming_uploads": 0,
        "recent_staged_uploads": 0,
        "old_staged_upload_bytes": 0,
        "unrecognized_entries": 0,
    }


@pytest.mark.parametrize(
    "arguments",
    [
        ["--min-age-hours", "0"],
        ["--min-age-hours", "abc"],
        ["--scan-limit", "0"],
        ["--scan-limit", "10001"],
        ["--scan-limit", "abc"],
        ["--apply"],
    ],
)
def test_rejects_invalid_or_destructive_arguments(
    arguments: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["blob_audit", *arguments])

    with pytest.raises(SystemExit) as error:
        blob_audit.main()

    assert error.value.code == 2
