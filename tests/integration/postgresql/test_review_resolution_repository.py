"""SQLAlchemy manual-review resolution repository integration tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.outbound.postgresql.database import Database, create_database
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyProcessingRunRepository,
    SqlAlchemyReviewResolutionRepository,
)
from document_platform.domain.documents import Document
from document_platform.domain.processing import (
    ProcessingRun,
    ReviewResolution,
    ReviewResolutionDecision,
)
from document_platform.settings import Settings

AT = datetime(2026, 9, 17, 14, 0, tzinfo=UTC)
DOCUMENT_ID = UUID("a8a8a8a8-a8a8-48a8-88a8-a8a8a8a8a8a8")
RUN_ID = UUID("a9a9a9a9-a9a9-49a9-89a9-a9a9a9a9a9a9")


def database_for(postgres_url: str) -> Database:
    return create_database(Settings(environment="test", database_url=PostgresDsn(postgres_url)))


@pytest.mark.anyio
async def test_adds_and_loads_an_immutable_review_resolution(
    migrated_postgres_url: str,
) -> None:
    database = database_for(migrated_postgres_url)
    document = Document.accept_pdf(
        document_id=DOCUMENT_ID,
        original_filename="review-resolution-test.pdf",
        size_bytes=10_000,
        page_count=1,
        content_sha256=DOCUMENT_ID.hex * 2,
        storage_key=f"blobs/{DOCUMENT_ID}",
        accepted_at=AT,
    )
    run = ProcessingRun.queue(run_id=RUN_ID, document_id=DOCUMENT_ID, queued_at=AT)
    resolution = ReviewResolution(
        processing_run_id=RUN_ID,
        decision=ReviewResolutionDecision.APPROVE,
        reviewer_id="operator-42",
        review_note="Validated against the supplier record.",
        resolved_at=AT,
    )
    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            await SqlAlchemyProcessingRunRepository(session).add(run)
            await SqlAlchemyReviewResolutionRepository(session).add(resolution)
        async with database.sessions() as session:
            loaded = await SqlAlchemyReviewResolutionRepository(session).get(RUN_ID)
    finally:
        await database.dispose()

    assert loaded == resolution
