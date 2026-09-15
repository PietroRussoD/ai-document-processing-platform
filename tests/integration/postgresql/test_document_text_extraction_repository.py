"""SQLAlchemy document-text extraction repository integration tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.outbound.postgresql.database import Database, create_database
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyDocumentTextExtractionRepository,
    SqlAlchemyProcessingRunRepository,
)
from document_platform.domain.documents import Document
from document_platform.domain.processing import (
    DocumentTextExtraction,
    EmbeddedTextQuality,
    ProcessingRun,
    TextExtractionMethod,
)
from document_platform.settings import Settings

RECORDED_AT = datetime(2026, 9, 15, 13, 0, tzinfo=UTC)
DOCUMENT_ID = UUID("61616161-6161-4161-8161-616161616161")
RUN_ID = UUID("62626262-6262-4262-8262-626262626262")


def database_for(postgres_url: str) -> Database:
    return create_database(Settings(environment="test", database_url=PostgresDsn(postgres_url)))


@pytest.mark.anyio
async def test_adds_and_loads_an_immutable_document_text_extraction(
    migrated_postgres_url: str,
) -> None:
    database = database_for(migrated_postgres_url)
    document = Document.accept_pdf(
        document_id=DOCUMENT_ID,
        original_filename="text-extraction-test.pdf",
        size_bytes=10_000,
        page_count=1,
        content_sha256=DOCUMENT_ID.hex * 2,
        storage_key=f"blobs/{DOCUMENT_ID}",
        accepted_at=RECORDED_AT,
    )
    run = ProcessingRun.queue(run_id=RUN_ID, document_id=DOCUMENT_ID, queued_at=RECORDED_AT)
    extraction = DocumentTextExtraction(
        processing_run_id=RUN_ID,
        method=TextExtractionMethod.PYMUPDF,
        text="Invoice 42",
        page_count=1,
        character_count=10,
        non_whitespace_character_count=9,
        quality=EmbeddedTextQuality.OCR_RECOMMENDED,
        extracted_at=RECORDED_AT,
    )

    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            await SqlAlchemyProcessingRunRepository(session).add(run)
            await SqlAlchemyDocumentTextExtractionRepository(session).add(extraction)

        async with database.sessions() as session:
            loaded = await SqlAlchemyDocumentTextExtractionRepository(session).get(RUN_ID)
    finally:
        await database.dispose()

    assert loaded == extraction
