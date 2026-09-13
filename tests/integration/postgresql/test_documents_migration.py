"""Documents schema migration tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import PostgresDsn
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.settings import Settings

EXPECTED_COLUMNS = {
    "id",
    "original_filename",
    "media_type",
    "size_bytes",
    "page_count",
    "content_sha256",
    "storage_key",
    "status",
    "accepted_at",
    "status_changed_at",
    "version",
}


@pytest.mark.anyio
async def test_creates_the_documents_schema(migrated_postgres_url: str) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )

    try:
        async with database.sessions() as session:
            columns = await session.scalars(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'documents'
                    """
                )
            )
    finally:
        await database.dispose()

    assert set(columns) == EXPECTED_COLUMNS


@pytest.mark.anyio
async def test_rejects_an_unknown_document_status(migrated_postgres_url: str) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )

    try:
        with pytest.raises(IntegrityError):
            async with database.engine.begin() as connection:
                await connection.execute(
                    text(
                        """
                        INSERT INTO documents (
                            id, original_filename, media_type, size_bytes, page_count,
                            content_sha256, storage_key, status, accepted_at,
                            status_changed_at, version
                        ) VALUES (
                            :id, :original_filename, :media_type, :size_bytes, :page_count,
                            :content_sha256, :storage_key, :status, :accepted_at,
                            :status_changed_at, :version
                        )
                        """
                    ),
                    {
                        "id": UUID("be839b1b-7a68-4b8d-a183-81bf5eeae6e3"),
                        "original_filename": "invalid-status.pdf",
                        "media_type": "application/pdf",
                        "size_bytes": 1,
                        "page_count": 1,
                        "content_sha256": "b" * 64,
                        "storage_key": "blobs/invalid-status",
                        "status": "UNKNOWN",
                        "accepted_at": datetime(2026, 9, 13, 9, 0, tzinfo=UTC),
                        "status_changed_at": datetime(2026, 9, 13, 9, 0, tzinfo=UTC),
                        "version": 0,
                    },
                )
    finally:
        await database.dispose()
