"""Read-only local blob audit backed by PostgreSQL references."""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.outbound.filesystem import LocalBlobStore
from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.adapters.outbound.postgresql.repositories import SqlAlchemyDocumentRepository
from document_platform.application.ports import StoredBlob
from document_platform.blob_audit import summarize_blob_candidates
from document_platform.domain.documents import Document
from document_platform.settings import Settings


@pytest.mark.anyio
async def test_reports_only_old_unreferenced_blobs_without_deleting_files(
    migrated_postgres_url: str, tmp_path: Path
) -> None:
    now = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
    root = tmp_path / "data"
    settings = Settings(
        environment="test",
        database_url=PostgresDsn(migrated_postgres_url),
        storage_root=root,
    )
    store = LocalBlobStore(root, max_bytes=1_024)
    source = tmp_path / "source.pdf"
    stored: list[StoredBlob] = []
    for content, age_hours in ((b"referenced", 48), (b"orphan", 48), (b"recent", 1)):
        source.write_bytes(content)
        blob = await store.store(source)
        path = root / blob.key
        modified_at = (now - timedelta(hours=age_hours)).timestamp()
        os.utime(path, (modified_at, modified_at))
        stored.append(blob)

    (root / "temporary" / "pending.upload").write_bytes(b"pending")
    (root / "incoming").mkdir()
    (root / "incoming" / "request.upload").write_bytes(b"request")
    database = create_database(settings)
    try:
        referenced_blob = stored[0]
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(
                Document.accept_pdf(
                    document_id=uuid4(),
                    original_filename="referenced.pdf",
                    size_bytes=referenced_blob.size_bytes,
                    page_count=1,
                    content_sha256=referenced_blob.content_sha256,
                    storage_key=referenced_blob.key,
                    accepted_at=now - timedelta(days=3),
                )
            )
    finally:
        await database.dispose()

    report = await summarize_blob_candidates(
        settings=settings, now=now, min_age_hours=24, scan_limit=100
    )

    assert report.published_blobs == 3
    assert report.checked_old_blobs == 2
    assert report.recent_blobs == 1
    assert report.potential_orphans == 1
    assert report.potential_orphan_bytes == stored[1].size_bytes
    assert report.temporary_uploads == 1
    assert report.incoming_uploads == 1
    assert not report.scan_truncated
    assert all((root / blob.key).is_file() for blob in stored)


@pytest.mark.anyio
async def test_marks_a_limited_audit_as_incomplete(
    migrated_postgres_url: str, tmp_path: Path
) -> None:
    settings = Settings(
        environment="test",
        database_url=PostgresDsn(migrated_postgres_url),
        storage_root=tmp_path / "data",
    )
    source = tmp_path / "source.pdf"
    source.write_bytes(b"one blob")
    await LocalBlobStore(settings.storage_root, max_bytes=1_024).store(source)

    report = await summarize_blob_candidates(
        settings=settings,
        now=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
        min_age_hours=24,
        scan_limit=1,
    )

    assert report.scan_truncated
    assert report.scanned_entries == 1
    assert report.published_blobs == 0
