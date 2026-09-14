"""Upload-idempotency schema migration tests."""

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
    "idempotency_key",
    "request_fingerprint",
    "processing_run_id",
    "recorded_at",
}
RECORDED_AT = datetime(2026, 9, 14, 13, 0, tzinfo=UTC)


async def _insert_document_and_run(
    connection: AsyncConnection,
    document_id: UUID,
    run_id: UUID,
) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO documents (
                id, original_filename, media_type, size_bytes, page_count,
                content_sha256, storage_key, status, accepted_at,
                status_changed_at, version
            ) VALUES (
                :document_id, 'idempotency-test.pdf', 'application/pdf', 1, 1,
                :content_sha256, :storage_key, 'UPLOADED', :recorded_at,
                :recorded_at, 0
            )
            """
        ),
        {
            "document_id": document_id,
            "content_sha256": document_id.hex * 2,
            "storage_key": f"blobs/{document_id}",
            "recorded_at": RECORDED_AT,
        },
    )
    await connection.execute(
        text(
            """
            INSERT INTO processing_runs (
                id, document_id, status, queued_at, started_at,
                status_changed_at, finished_at, attempt_count, version
            ) VALUES (
                :run_id, :document_id, 'QUEUED', :recorded_at, NULL,
                :recorded_at, NULL, 0, 0
            )
            """
        ),
        {"run_id": run_id, "document_id": document_id, "recorded_at": RECORDED_AT},
    )


@pytest.mark.anyio
async def test_creates_the_upload_idempotency_schema(migrated_postgres_url: str) -> None:
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
                    WHERE table_schema = 'public'
                      AND table_name = 'upload_idempotency_records'
                    """
                )
            )
    finally:
        await database.dispose()

    assert set(columns) == EXPECTED_COLUMNS


@pytest.mark.anyio
async def test_cascades_run_deletion_to_its_idempotency_record(
    migrated_postgres_url: str,
) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    document_id = UUID("17171717-1717-4717-8717-171717171717")
    run_id = UUID("18181818-1818-4818-8818-181818181818")

    try:
        async with database.engine.begin() as connection:
            await _insert_document_and_run(connection, document_id, run_id)
            await connection.execute(
                text(
                    """
                    INSERT INTO upload_idempotency_records (
                        idempotency_key, request_fingerprint, processing_run_id, recorded_at
                    ) VALUES ('cascade-test', :fingerprint, :run_id, :recorded_at)
                    """
                ),
                {"fingerprint": "a" * 64, "run_id": run_id, "recorded_at": RECORDED_AT},
            )
            await connection.execute(
                text("DELETE FROM processing_runs WHERE id = :run_id"),
                {"run_id": run_id},
            )
            remaining = await connection.scalar(
                text(
                    "SELECT count(*) FROM upload_idempotency_records "
                    "WHERE idempotency_key = 'cascade-test'"
                )
            )
    finally:
        await database.dispose()

    assert remaining == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("key", "request_fingerprint"),
    [(" padded", "a" * 64), ("valid-key", "invalid")],
)
async def test_rejects_invalid_idempotency_data(
    migrated_postgres_url: str,
    key: str,
    request_fingerprint: str,
) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    document_id = UUID("19191919-1919-4919-8919-191919191919")
    run_id = UUID("20202020-2020-4020-8020-202020202020")

    try:
        with pytest.raises(IntegrityError):
            async with database.engine.begin() as connection:
                await _insert_document_and_run(connection, document_id, run_id)
                await connection.execute(
                    text(
                        """
                        INSERT INTO upload_idempotency_records (
                            idempotency_key, request_fingerprint, processing_run_id, recorded_at
                        ) VALUES (:key, :request_fingerprint, :run_id, :recorded_at)
                        """
                    ),
                    {
                        "key": key,
                        "request_fingerprint": request_fingerprint,
                        "run_id": run_id,
                        "recorded_at": RECORDED_AT,
                    },
                )
    finally:
        await database.dispose()
