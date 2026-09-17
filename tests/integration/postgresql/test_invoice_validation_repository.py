"""SQLAlchemy invoice-validation repository integration tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.outbound.postgresql.database import Database, create_database
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyInvoiceValidationRepository,
    SqlAlchemyProcessingRunRepository,
)
from document_platform.domain.documents import Document
from document_platform.domain.processing import (
    InvoiceValidation,
    InvoiceValidationDecision,
    InvoiceValidationIssue,
    ProcessingRun,
)
from document_platform.settings import Settings

AT = datetime(2026, 9, 17, 9, 0, tzinfo=UTC)
DOCUMENT_ID = UUID("c6c6c6c6-c6c6-46c6-86c6-c6c6c6c6c6c6")
RUN_ID = UUID("c7c7c7c7-c7c7-47c7-87c7-c7c7c7c7c7c7")


def database_for(postgres_url: str) -> Database:
    return create_database(Settings(environment="test", database_url=PostgresDsn(postgres_url)))


@pytest.mark.anyio
async def test_adds_and_loads_an_immutable_invoice_validation(
    migrated_postgres_url: str,
) -> None:
    database = database_for(migrated_postgres_url)
    document = Document.accept_pdf(
        document_id=DOCUMENT_ID,
        original_filename="invoice-validation-test.pdf",
        size_bytes=10_000,
        page_count=1,
        content_sha256=DOCUMENT_ID.hex * 2,
        storage_key=f"blobs/{DOCUMENT_ID}",
        accepted_at=AT,
    )
    run = ProcessingRun.queue(run_id=RUN_ID, document_id=DOCUMENT_ID, queued_at=AT)
    validation = InvoiceValidation(
        processing_run_id=RUN_ID,
        decision=InvoiceValidationDecision.REVIEW_REQUIRED,
        issues=(
            InvoiceValidationIssue.MISSING_CURRENCY,
            InvoiceValidationIssue.MISSING_TOTAL_AMOUNT,
        ),
        validated_at=AT,
    )
    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            await SqlAlchemyProcessingRunRepository(session).add(run)
            await SqlAlchemyInvoiceValidationRepository(session).add(validation)
        async with database.sessions() as session:
            loaded = await SqlAlchemyInvoiceValidationRepository(session).get(RUN_ID)
    finally:
        await database.dispose()

    assert loaded == validation
