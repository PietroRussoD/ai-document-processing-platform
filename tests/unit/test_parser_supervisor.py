"""Parser Job supervisor completion marker tests."""

from pathlib import Path

import pytest

import document_platform.parser_supervisor as supervisor


@pytest.mark.parametrize(("outcome", "expected_exit"), [("success", 0), ("failure", 1)])
def test_wait_exits_with_controller_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
    expected_exit: int,
) -> None:
    marker = tmp_path / "outcome"
    marker.write_text(outcome, encoding="ascii")
    monkeypatch.setattr(supervisor, "_OUTCOME_FILE", marker)
    monkeypatch.setattr("sys.argv", ["parser_supervisor", "wait"])

    assert supervisor.main() == expected_exit


def test_complete_creates_one_bounded_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "outcome"
    monkeypatch.setattr(supervisor, "_OUTCOME_FILE", marker)
    monkeypatch.setattr("sys.argv", ["parser_supervisor", "complete", "--outcome", "success"])

    assert supervisor.main() == 0
    assert marker.read_text(encoding="ascii") == "success"
    assert supervisor.main() == 1
