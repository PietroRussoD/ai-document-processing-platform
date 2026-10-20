"""Wait for a trusted controller to finish one parser Job."""

import argparse
import sys
import time
from pathlib import Path

_OUTCOME_FILE = Path("/scratch/outcome")
_CGROUP_MEMORY_EVENTS = Path("/sys/fs/cgroup/memory.events")


def _read_oom_kill_count() -> int | None:
    try:
        for line in _CGROUP_MEMORY_EVENTS.read_text(encoding="ascii").splitlines():
            name, raw_count = line.split()
            if name == "oom_kill":
                count = int(raw_count)
                return count if count >= 0 else None
    except (OSError, UnicodeError, ValueError):
        return None
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("wait")
    commands.add_parser("oom-count")
    complete = commands.add_parser("complete")
    complete.add_argument("--outcome", choices=("success", "failure"), required=True)
    args = parser.parse_args()

    if args.command == "oom-count":
        count = _read_oom_kill_count()
        if count is None:
            return 3
        print(count)
        return 0

    if args.command == "complete":
        try:
            with _OUTCOME_FILE.open("x", encoding="ascii") as marker:
                marker.write(args.outcome)
        except OSError:
            return 1
        return 0

    while not _OUTCOME_FILE.exists():
        time.sleep(0.1)
    try:
        outcome = _OUTCOME_FILE.read_text(encoding="ascii")
    except OSError:
        return 1
    return 0 if outcome == "success" else 1 if outcome == "failure" else 2


if __name__ == "__main__":
    sys.exit(main())
