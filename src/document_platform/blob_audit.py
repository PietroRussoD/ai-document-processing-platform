"""Report possible local blob orphans without deleting files."""

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from document_platform.adapters.outbound.filesystem import LocalStorageInventory
from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.adapters.outbound.postgresql.queries import SqlAlchemyBlobReferenceReader
from document_platform.application.ports import BlobIdentity
from document_platform.settings import Settings

MAX_SCAN_ENTRIES = 10_000


@dataclass(frozen=True, slots=True)
class BlobAuditReport:
    older_than: datetime
    scan_limit: int
    scanned_entries: int
    scan_truncated: bool
    published_blobs: int
    recent_blobs: int
    checked_old_blobs: int
    potential_orphans: int
    potential_orphan_bytes: int
    temporary_uploads: int
    incoming_uploads: int
    unrecognized_entries: int


async def summarize_blob_candidates(
    *, settings: Settings, now: datetime, min_age_hours: int, scan_limit: int
) -> BlobAuditReport:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if min_age_hours < 1:
        raise ValueError("min_age_hours must be positive")
    if not 1 <= scan_limit <= MAX_SCAN_ENTRIES:
        raise ValueError(f"scan_limit must be between 1 and {MAX_SCAN_ENTRIES}")

    older_than = now - timedelta(hours=min_age_hours)
    inventory = LocalStorageInventory(settings.storage_root).scan(limit=scan_limit)
    old_blobs = [blob for blob in inventory.published_blobs if blob.modified_at < older_than]
    identities = frozenset(BlobIdentity(blob.key, blob.content_sha256) for blob in old_blobs)

    database = create_database(settings)
    try:
        referenced = await SqlAlchemyBlobReferenceReader(database.sessions).find_referenced(
            identities
        )
    finally:
        await database.dispose()

    candidates = [
        blob for blob in old_blobs if BlobIdentity(blob.key, blob.content_sha256) not in referenced
    ]
    return BlobAuditReport(
        older_than=older_than,
        scan_limit=scan_limit,
        scanned_entries=inventory.scanned_entries,
        scan_truncated=inventory.truncated,
        published_blobs=len(inventory.published_blobs),
        recent_blobs=len(inventory.published_blobs) - len(old_blobs),
        checked_old_blobs=len(old_blobs),
        potential_orphans=len(candidates),
        potential_orphan_bytes=sum(blob.size_bytes for blob in candidates),
        temporary_uploads=inventory.temporary_uploads,
        incoming_uploads=inventory.incoming_uploads,
        unrecognized_entries=inventory.unrecognized_entries,
    )


def _positive_hours(value: str) -> int:
    try:
        hours = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("min age hours must be an integer") from error
    if hours < 1:
        raise argparse.ArgumentTypeError("min age hours must be positive")
    return hours


def _scan_limit(value: str) -> int:
    try:
        limit = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("scan limit must be an integer") from error
    if not 1 <= limit <= MAX_SCAN_ENTRIES:
        raise argparse.ArgumentTypeError(f"scan limit must be between 1 and {MAX_SCAN_ENTRIES}")
    return limit


async def _print_report(*, min_age_hours: int, scan_limit: int) -> None:
    report = await summarize_blob_candidates(
        settings=Settings(),
        now=datetime.now(UTC),
        min_age_hours=min_age_hours,
        scan_limit=scan_limit,
    )
    print(
        json.dumps(
            {
                "mode": "report-only",
                "older_than": report.older_than.isoformat(),
                "scan_limit": report.scan_limit,
                "scanned_entries": report.scanned_entries,
                "scan_truncated": report.scan_truncated,
                "published_blobs": report.published_blobs,
                "recent_blobs": report.recent_blobs,
                "checked_old_blobs": report.checked_old_blobs,
                "potential_orphans": report.potential_orphans,
                "potential_orphan_bytes": report.potential_orphan_bytes,
                "temporary_uploads": report.temporary_uploads,
                "incoming_uploads": report.incoming_uploads,
                "unrecognized_entries": report.unrecognized_entries,
            },
            sort_keys=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Report possible local blob orphans.")
    parser.add_argument("--min-age-hours", type=_positive_hours, default=24)
    parser.add_argument("--scan-limit", type=_scan_limit, default=1_000)
    arguments = parser.parse_args()
    asyncio.run(
        _print_report(min_age_hours=arguments.min_age_hours, scan_limit=arguments.scan_limit)
    )


if __name__ == "__main__":
    main()
