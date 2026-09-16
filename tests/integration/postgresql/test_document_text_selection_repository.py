"""SQLAlchemy canonical-text selection repository integration tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.outbound.postgresql.database import Database, create_database
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyDocumentTextSelectionRepository,
    SqlAlchemyProcessingRunRepository,
)
from document_platform.domain.documents import Document
from document_platform.domain.processing import (
    DocumentTextSelection,
    ProcessingRun,
    ProcessingTextSelectionReason,
    ProcessingTextSource,
)
from document_platform.settings import Settings

AT = datetime(2026, 9, 16, 10, 0, tzinfo=UTC)
DOCUMENT_ID = UUID("94949494-9494-4494-8494-949494949494")
RUN_ID = UUID("95959595-9595-4595-8595-959595959595")


def database_for(postgres_url: str) -> Database:
    return create_database(Settings(environment="test", database_url=PostgresDsn(postgres_url)))


@pytest.mark.anyio
async def test_adds_and_loads_an_immutable_text_selection(migrated_postgres_url: str) -> None:
    database = database_for(migrated_postgres_url)
    document = Document.accept_pdf(
        document_id=DOCUMENT_ID,
        original_filename="selection-test.pdf",
        size_bytes=10_000,
        page_count=1,
        content_sha256=DOCUMENT_ID.hex * 2,
        storage_key=f"blobs/{DOCUMENT_ID}",
        accepted_at=AT,
    )
    run = ProcessingRun.queue(run_id=RUN_ID, document_id=DOCUMENT_ID, queued_at=AT)
    selection = DocumentTextSelection(
        processing_run_id=RUN_ID,
        source=ProcessingTextSource.EMBEDDED,
        reason=ProcessingTextSelectionReason.EMBEDDED_SUFFICIENT,
        selected_at=AT,
    )
    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            await SqlAlchemyProcessingRunRepository(session).add(run)
            await SqlAlchemyDocumentTextSelectionRepository(session).add(selection)
        async with database.sessions() as session:
            loaded = await SqlAlchemyDocumentTextSelectionRepository(session).get(RUN_ID)
    finally:
        await database.dispose()

    assert loaded == selection
