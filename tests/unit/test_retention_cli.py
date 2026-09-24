"""Command-line behavior for explicit document retention."""

import json
import sys
from datetime import UTC, datetime, timedelta

import pytest

from document_platform import retention
from document_platform.application.ports import DocumentRetentionSnapshot
from document_platform.domain.documents import DocumentStatus


class FakeDatabase:
    def __init__(self) -> None:
        self.sessions = object()
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


class FakeReader:
    def __init__(self, snapshot: DocumentRetentionSnapshot) -> None:
        self.snapshot = snapshot
        self.cutoffs: list[datetime] = []

    async def summarize_candidates(self, *, cutoff: datetime) -> DocumentRetentionSnapshot:
        self.cutoffs.append(cutoff)
        return self.snapshot


class FakeDeleter:
    def __init__(self, snapshot: DocumentRetentionSnapshot) -> None:
        self.snapshot = snapshot
        self.cutoffs: list[datetime] = []

    async def delete_candidates(self, *, cutoff: datetime) -> DocumentRetentionSnapshot:
        self.cutoffs.append(cutoff)
        return self.snapshot


@pytest.mark.parametrize(
    ("extra_arguments", "mode", "result_prefix"),
    [([], "dry-run", "eligible"), (["--apply"], "apply", "deleted")],
)
def test_cli_selects_the_requested_mode_and_prints_aggregate_json(
    extra_arguments: list[str],
    mode: str,
    result_prefix: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    snapshot = DocumentRetentionSnapshot(
        counts_by_status={DocumentStatus.FAILED: 1, DocumentStatus.APPROVED: 2},
        total_size_bytes=123,
    )
    database = FakeDatabase()
    reader = FakeReader(snapshot)
    deleter = FakeDeleter(snapshot)

    def create_test_database(_settings: object) -> FakeDatabase:
        return database

    def create_test_reader(_sessions: object) -> FakeReader:
        return reader

    def create_test_deleter(_sessions: object) -> FakeDeleter:
        return deleter

    monkeypatch.setattr(retention, "Settings", lambda: object())
    monkeypatch.setattr(retention, "create_database", create_test_database)
    monkeypatch.setattr(retention, "SqlAlchemyDocumentRetentionReader", create_test_reader)
    monkeypatch.setattr(retention, "SqlAlchemyDocumentRetentionDeleter", create_test_deleter)
    monkeypatch.setattr(sys, "argv", ["retention", "--retention-days", "30", *extra_arguments])

    before = datetime.now(UTC)
    retention.main()
    after = datetime.now(UTC)

    output = json.loads(capsys.readouterr().out)
    cutoff_text = output.pop("cutoff")
    assert output == {
        "mode": mode,
        "retention_days": 30,
        f"{result_prefix}_documents": 3,
        f"{result_prefix}_bytes": 123,
        f"{result_prefix}_by_status": {"APPROVED": 2, "FAILED": 1},
    }
    cutoff = datetime.fromisoformat(cutoff_text)
    assert before - timedelta(days=30) <= cutoff <= after - timedelta(days=30)
    assert reader.cutoffs == ([cutoff] if mode == "dry-run" else [])
    assert deleter.cutoffs == ([cutoff] if mode == "apply" else [])
    assert database.disposed


@pytest.mark.parametrize("days", ["0", "-1", "abc"])
def test_cli_rejects_invalid_retention_days(
    days: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["retention", "--retention-days", days])

    with pytest.raises(SystemExit) as error:
        retention.main()

    assert error.value.code == 2
    assert "retention days" in capsys.readouterr().err
