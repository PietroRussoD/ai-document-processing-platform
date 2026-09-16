"""SQLAlchemy invoice-extraction repository integration tests."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.outbound.postgresql.database import Database, create_database
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyInvoiceExtractionRepository,
    SqlAlchemyProcessingRunRepository,
)
from document_platform.domain.documents import Document
from document_platform.domain.processing import (
    InvoiceExtraction,
    InvoiceExtractionMethod,
    ProcessingRun,
)
from document_platform.settings import Settings

AT = datetime(2026, 9, 16, 21, 0, tzinfo=UTC)
DOCUMENT_ID = UUID("d4d4d4d4-d4d4-44d4-84d4-d4d4d4d4d4d4")
RUN_ID = UUID("e5e5e5e5-e5e5-45e5-85e5-e5e5e5e5e5e5")


def database_for(postgres_url: str) -> Database:
    return create_database(Settings(environment="test", database_url=PostgresDsn(postgres_url)))


@pytest.mark.anyio
async def test_adds_and_loads_an_immutable_invoice_extraction(
    migrated_postgres_url: str,
) -> None:
    database = database_for(migrated_postgres_url)
    document = Document.accept_pdf(
        document_id=DOCUMENT_ID,
        original_filename="invoice-extraction-test.pdf",
        size_bytes=10_000,
        page_count=1,
        content_sha256=DOCUMENT_ID.hex * 2,
        storage_key=f"blobs/{DOCUMENT_ID}",
        accepted_at=AT,
    )
    run = ProcessingRun.queue(run_id=RUN_ID, document_id=DOCUMENT_ID, queued_at=AT)
    extraction = InvoiceExtraction(
        processing_run_id=RUN_ID,
        method=InvoiceExtractionMethod.DETERMINISTIC_RULES,
        invoice_number="INV-42",
        issue_date=date(2026, 9, 16),
        supplier_name="Acme Ltd",
        currency="EUR",
        total_amount=Decimal("12.5000"),
        extracted_at=AT,
    )
    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            await SqlAlchemyProcessingRunRepository(session).add(run)
            await SqlAlchemyInvoiceExtractionRepository(session).add(extraction)
        async with database.sessions() as session:
            loaded = await SqlAlchemyInvoiceExtractionRepository(session).get(RUN_ID)
    finally:
        await database.dispose()

    assert loaded == extraction
