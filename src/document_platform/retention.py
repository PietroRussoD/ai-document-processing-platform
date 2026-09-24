"""Preview or apply database-only document retention."""

import argparse
import asyncio
import json
from datetime import UTC, datetime

from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.adapters.outbound.postgresql.queries import (
    SqlAlchemyDocumentRetentionDeleter,
    SqlAlchemyDocumentRetentionReader,
)
from document_platform.application.commands import ApplyDocumentRetentionHandler
from document_platform.application.queries import SummarizeDocumentRetentionHandler
from document_platform.settings import Settings


def _positive_days(value: str) -> int:
    try:
        days = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("retention days must be an integer") from error
    if days < 1:
        raise argparse.ArgumentTypeError("retention days must be positive")
    return days


async def _print_report(retention_days: int, *, apply: bool) -> None:
    settings = Settings()
    database = create_database(settings)
    try:
        if apply:
            handler = ApplyDocumentRetentionHandler(
                SqlAlchemyDocumentRetentionDeleter(database.sessions),
                clock=lambda: datetime.now(UTC),
            )
        else:
            handler = SummarizeDocumentRetentionHandler(
                SqlAlchemyDocumentRetentionReader(database.sessions),
                clock=lambda: datetime.now(UTC),
            )
        report = await handler(retention_days=retention_days)
    finally:
        await database.dispose()

    snapshot = report.snapshot
    result_name = "deleted" if apply else "eligible"
    print(
        json.dumps(
            {
                "mode": "apply" if apply else "dry-run",
                "retention_days": report.retention_days,
                "cutoff": report.cutoff.isoformat(),
                f"{result_name}_documents": snapshot.document_count,
                f"{result_name}_bytes": snapshot.total_size_bytes,
                f"{result_name}_by_status": {
                    status.value: count
                    for status, count in sorted(
                        snapshot.counts_by_status.items(), key=lambda item: item[0].value
                    )
                },
            },
            sort_keys=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preview or delete terminal document records past their retention period."
    )
    parser.add_argument("--retention-days", required=True, type=_positive_days)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="delete eligible document records and their database-owned evidence",
    )
    arguments = parser.parse_args()
    asyncio.run(_print_report(arguments.retention_days, apply=arguments.apply))


if __name__ == "__main__":
    main()
