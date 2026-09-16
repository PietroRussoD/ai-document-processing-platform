"""SQLAlchemy document-classification repository integration tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.outbound.postgresql.database import Database, create_database
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentClassificationRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyProcessingRunRepository,
)
from document_platform.domain.documents import Document
from document_platform.domain.processing import (
    BusinessDocumentType,
    DocumentClassification,
    DocumentClassificationReason,
    ProcessingRun,
)
from document_platform.settings import Settings

AT = datetime(2026, 9, 16, 11, 0, tzinfo=UTC)
DOCUMENT_ID = UUID("a4a4a4a4-a4a4-44a4-84a4-a4a4a4a4a4a4")
RUN_ID = UUID("a5a5a5a5-a5a5-45a5-85a5-a5a5a5a5a5a5")


def database_for(postgres_url: str) -> Database:
    return create_database(Settings(environment="test", database_url=PostgresDsn(postgres_url)))


@pytest.mark.anyio
async def test_adds_and_loads_an_immutable_document_classification(
    migrated_postgres_url: str,
) -> None:
    database = database_for(migrated_postgres_url)
    document = Document.accept_pdf(
        document_id=DOCUMENT_ID,
        original_filename="classification-test.pdf",
        size_bytes=10_000,
        page_count=1,
        content_sha256=DOCUMENT_ID.hex * 2,
        storage_key=f"blobs/{DOCUMENT_ID}",
        accepted_at=AT,
    )
    run = ProcessingRun.queue(run_id=RUN_ID, document_id=DOCUMENT_ID, queued_at=AT)
    classification = DocumentClassification(
        processing_run_id=RUN_ID,
        document_type=BusinessDocumentType.INVOICE,
        reason=DocumentClassificationReason.KEYWORD_MATCHED,
        classified_at=AT,
    )
    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            await SqlAlchemyProcessingRunRepository(session).add(run)
            await SqlAlchemyDocumentClassificationRepository(session).add(classification)
        async with database.sessions() as session:
            loaded = await SqlAlchemyDocumentClassificationRepository(session).get(RUN_ID)
    finally:
        await database.dispose()

    assert loaded == classification
