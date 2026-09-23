"""Read-only CLI for previewing documents past their retention period."""

import argparse
import asyncio
import json
from datetime import UTC, datetime

from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.adapters.outbound.postgresql.queries import SqlAlchemyDocumentRetentionReader
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


async def _print_report(retention_days: int) -> None:
    settings = Settings()
    database = create_database(settings)
    try:
        handler = SummarizeDocumentRetentionHandler(
            SqlAlchemyDocumentRetentionReader(database.sessions),
            clock=lambda: datetime.now(UTC),
        )
        report = await handler(retention_days=retention_days)
    finally:
        await database.dispose()

    snapshot = report.snapshot
    print(
        json.dumps(
            {
                "mode": "dry-run",
                "retention_days": report.retention_days,
                "cutoff": report.cutoff.isoformat(),
                "eligible_documents": snapshot.document_count,
                "eligible_bytes": snapshot.total_size_bytes,
                "eligible_by_status": {
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
        description="Preview terminal documents older than a supplied retention period."
    )
    parser.add_argument("--retention-days", required=True, type=_positive_days)
    arguments = parser.parse_args()
    asyncio.run(_print_report(arguments.retention_days))


if __name__ == "__main__":
    main()
