"""SQLAlchemy invoice review-correction repository integration tests."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.outbound.postgresql.database import Database, create_database
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyInvoiceReviewCorrectionRepository,
    SqlAlchemyProcessingRunRepository,
    SqlAlchemyReviewResolutionRepository,
)
from document_platform.application.ports import InvoiceReviewCorrectionAlreadyExists
from document_platform.domain.documents import Document
from document_platform.domain.processing import (
    InvoiceReviewCorrection,
    InvoiceReviewCorrectionSource,
    InvoiceReviewField,
    InvoiceReviewFieldCorrection,
    ProcessingRun,
    ReviewResolution,
    ReviewResolutionDecision,
)
from document_platform.settings import Settings

AT = datetime(2026, 9, 18, 20, 0, tzinfo=UTC)
DOCUMENT_ID = UUID("d8d8d8d8-d8d8-48d8-88d8-d8d8d8d8d8d8")
RUN_ID = UUID("d9d9d9d9-d9d9-49d9-89d9-d9d9d9d9d9d9")
SECOND_DOCUMENT_ID = UUID("dadadada-dada-4ada-8ada-dadadadadada")
SECOND_RUN_ID = UUID("dbdbdbdb-dbdb-4bdb-8bdb-dbdbdbdbdbdb")


def database_for(postgres_url: str) -> Database:
    return create_database(Settings(environment="test", database_url=PostgresDsn(postgres_url)))


def document(document_id: UUID) -> Document:
    return Document.accept_pdf(
        document_id=document_id,
        original_filename="invoice-review-correction-test.pdf",
        size_bytes=10_000,
        page_count=1,
        content_sha256=document_id.hex * 2,
        storage_key=f"blobs/{document_id}",
        accepted_at=AT,
    )


def resolution(run_id: UUID) -> ReviewResolution:
    return ReviewResolution(
        processing_run_id=run_id,
        decision=ReviewResolutionDecision.APPROVE,
        reviewer_id="operator-42",
        review_note="Validated against the supplier record.",
        resolved_at=AT,
    )


def correction(run_id: UUID) -> InvoiceReviewCorrection:
    return InvoiceReviewCorrection(
        processing_run_id=run_id,
        corrections=(
            InvoiceReviewFieldCorrection(
                field=InvoiceReviewField.ISSUE_DATE,
                corrected_value=date(2026, 9, 18),
            ),
            InvoiceReviewFieldCorrection(
                field=InvoiceReviewField.TOTAL_AMOUNT,
                corrected_value=Decimal("39.98"),
                source=InvoiceReviewCorrectionSource.AI_PROPOSAL,
            ),
        ),
        corrected_at=AT,
    )


@pytest.mark.anyio
async def test_adds_and_loads_an_immutable_invoice_review_correction(
    migrated_postgres_url: str,
) -> None:
    database = database_for(migrated_postgres_url)
    expected = correction(RUN_ID)
    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document(DOCUMENT_ID))
            await SqlAlchemyProcessingRunRepository(session).add(
                ProcessingRun.queue(run_id=RUN_ID, document_id=DOCUMENT_ID, queued_at=AT)
            )
            await SqlAlchemyReviewResolutionRepository(session).add(resolution(RUN_ID))
            await SqlAlchemyInvoiceReviewCorrectionRepository(session).add(expected)
        async with database.sessions() as session:
            loaded = await SqlAlchemyInvoiceReviewCorrectionRepository(session).get(RUN_ID)
    finally:
        await database.dispose()

    assert loaded == expected


@pytest.mark.anyio
async def test_rejects_a_second_correction_for_the_same_run(
    migrated_postgres_url: str,
) -> None:
    database = database_for(migrated_postgres_url)
    expected = correction(SECOND_RUN_ID)
    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document(SECOND_DOCUMENT_ID))
            await SqlAlchemyProcessingRunRepository(session).add(
                ProcessingRun.queue(
                    run_id=SECOND_RUN_ID,
                    document_id=SECOND_DOCUMENT_ID,
                    queued_at=AT,
                )
            )
            await SqlAlchemyReviewResolutionRepository(session).add(resolution(SECOND_RUN_ID))
            await SqlAlchemyInvoiceReviewCorrectionRepository(session).add(expected)
        async with database.sessions.begin() as session:
            with pytest.raises(InvoiceReviewCorrectionAlreadyExists):
                await SqlAlchemyInvoiceReviewCorrectionRepository(session).add(expected)
    finally:
        await database.dispose()
