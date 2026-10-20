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


def test_oom_count_reports_the_cgroup_v2_counter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    events = tmp_path / "memory.events"
    events.write_text("low 0\nhigh 0\nmax 0\noom 1\noom_kill 2\n", encoding="ascii")
    monkeypatch.setattr(supervisor, "_CGROUP_MEMORY_EVENTS", events)
    monkeypatch.setattr("sys.argv", ["parser_supervisor", "oom-count"])

    assert supervisor.main() == 0
    assert capsys.readouterr().out == "2\n"


def test_oom_count_reports_unsupported_cgroup_counter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    events = tmp_path / "memory.events"
    events.write_text("low 0\nhigh 0\n", encoding="ascii")
    monkeypatch.setattr(supervisor, "_CGROUP_MEMORY_EVENTS", events)
    monkeypatch.setattr("sys.argv", ["parser_supervisor", "oom-count"])

    assert supervisor.main() == 3
    assert capsys.readouterr().out == ""
