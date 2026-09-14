"""PostgreSQL document-status read-model integration tests."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.adapters.outbound.postgresql.queries import SqlAlchemyDocumentStatusReader
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyProcessingRunRepository,
)
from document_platform.domain.documents import Document
from document_platform.domain.processing import ProcessingRun
from document_platform.settings import Settings

ACCEPTED_AT = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)


@pytest.mark.anyio
async def test_returns_the_document_with_its_most_recent_run(
    migrated_postgres_url: str,
) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    document_id = uuid4()
    first_run_id = uuid4()
    latest_run_id = uuid4()
    document = Document.accept_pdf(
        document_id=document_id,
        original_filename="supplier-invoice.pdf",
        size_bytes=42_000,
        page_count=2,
        content_sha256="b" * 64,
        storage_key="blobs/sha256/bb/" + "b" * 64,
        accepted_at=ACCEPTED_AT,
    )
    first_run = ProcessingRun.queue(
        run_id=first_run_id,
        document_id=document_id,
        queued_at=ACCEPTED_AT,
    )
    latest_run = ProcessingRun.queue(
        run_id=latest_run_id,
        document_id=document_id,
        queued_at=ACCEPTED_AT + timedelta(minutes=5),
    )

    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            runs = SqlAlchemyProcessingRunRepository(session)
            await runs.add(first_run)
            await runs.add(latest_run)

        reader = SqlAlchemyDocumentStatusReader(database.sessions)
        result = await reader.get(document_id)
        missing = await reader.get(uuid4())
    finally:
        await database.dispose()

    assert result is not None
    assert result.id == document_id
    assert result.original_filename == "supplier-invoice.pdf"
    assert result.current_run.id == latest_run_id
    assert result.current_run.queued_at == latest_run.queued_at
    assert missing is None
