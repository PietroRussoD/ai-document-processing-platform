"""Wait for a trusted controller to finish one parser Job."""

import argparse
import sys
import time
from pathlib import Path

_OUTCOME_FILE = Path("/scratch/outcome")


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("wait")
    complete = commands.add_parser("complete")
    complete.add_argument("--outcome", choices=("success", "failure"), required=True)
    args = parser.parse_args()

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
