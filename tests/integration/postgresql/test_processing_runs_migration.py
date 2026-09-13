"""Processing-runs schema migration tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import PostgresDsn
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.settings import Settings

EXPECTED_COLUMNS = {
    "id",
    "document_id",
    "status",
    "queued_at",
    "started_at",
    "status_changed_at",
    "finished_at",
    "attempt_count",
    "version",
}
RECORDED_AT = datetime(2026, 9, 13, 13, 0, tzinfo=UTC)


async def insert_document(connection: AsyncConnection, document_id: UUID) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO documents (
                id, original_filename, media_type, size_bytes, page_count,
                content_sha256, storage_key, status, accepted_at,
                status_changed_at, version
            ) VALUES (
                :id, 'processing-run-test.pdf', 'application/pdf', 1, 1,
                :content_sha256, :storage_key, 'UPLOADED', :recorded_at,
                :recorded_at, 0
            )
            """
        ),
        {
            "id": document_id,
            "content_sha256": document_id.hex * 2,
            "storage_key": f"blobs/{document_id}",
            "recorded_at": RECORDED_AT,
        },
    )


async def insert_queued_run(
    connection: AsyncConnection,
    *,
    run_id: UUID,
    document_id: UUID,
    attempt_count: int = 0,
) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO processing_runs (
                id, document_id, status, queued_at, started_at,
                status_changed_at, finished_at, attempt_count, version
            ) VALUES (
                :id, :document_id, 'QUEUED', :recorded_at, NULL,
                :recorded_at, NULL, :attempt_count, 0
            )
            """
        ),
        {
            "id": run_id,
            "document_id": document_id,
            "recorded_at": RECORDED_AT,
            "attempt_count": attempt_count,
        },
    )


@pytest.mark.anyio
async def test_creates_the_processing_runs_schema(migrated_postgres_url: str) -> None:
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
                    WHERE table_schema = 'public' AND table_name = 'processing_runs'
                    """
                )
            )
    finally:
        await database.dispose()

    assert set(columns) == EXPECTED_COLUMNS


@pytest.mark.anyio
async def test_cascades_document_deletion_to_processing_runs(
    migrated_postgres_url: str,
) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    document_id = UUID("98989898-9898-4898-8898-989898989898")
    run_id = UUID("99999999-9999-4999-8999-999999999999")

    try:
        async with database.engine.begin() as connection:
            await insert_document(connection, document_id)
            await insert_queued_run(connection, run_id=run_id, document_id=document_id)
            await connection.execute(
                text("DELETE FROM documents WHERE id = :id"),
                {"id": document_id},
            )
            remaining = await connection.scalar(
                text("SELECT count(*) FROM processing_runs WHERE id = :id"),
                {"id": run_id},
            )
    finally:
        await database.dispose()

    assert remaining == 0


@pytest.mark.anyio
async def test_rejects_attempts_on_an_unstarted_run(migrated_postgres_url: str) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    document_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")

    try:
        with pytest.raises(IntegrityError):
            async with database.engine.begin() as connection:
                await insert_document(connection, document_id)
                await insert_queued_run(
                    connection,
                    run_id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
                    document_id=document_id,
                    attempt_count=1,
                )
    finally:
        await database.dispose()
