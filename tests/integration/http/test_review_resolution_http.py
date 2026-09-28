"""HTTP integration tests for authenticated document-review resolution."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import PostgresDsn, SecretStr

from document_platform.adapters.outbound.postgresql.database import Database
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyInvoiceExtractionRepository,
    SqlAlchemyProcessingRunRepository,
)
from document_platform.bootstrap import create_app
from document_platform.domain.documents import Document
from document_platform.domain.processing import (
    InvoiceExtraction,
    InvoiceExtractionMethod,
    ProcessingRun,
)
from document_platform.settings import Settings

TOKEN = "review-operator-token-with-at-least-thirty-two-characters"
DOCUMENT_ID = UUID("c8c8c8c8-c8c8-48c8-88c8-c8c8c8c8c8c8")
RUN_ID = UUID("c9c9c9c9-c9c9-49c9-89c9-c9c9c9c9c9c9")
QUEUED_AT = datetime(2026, 9, 17, 16, 0, tzinfo=UTC)
STARTED_AT = datetime(2026, 9, 17, 16, 1, tzinfo=UTC)
REVIEWED_AT = datetime(2026, 9, 17, 16, 2, tzinfo=UTC)


def review_required_document() -> Document:
    return (
        Document.accept_pdf(
            document_id=DOCUMENT_ID,
            original_filename="review.pdf",
            size_bytes=10_000,
            page_count=1,
            content_sha256=DOCUMENT_ID.hex * 2,
            storage_key=f"blobs/{DOCUMENT_ID}",
            accepted_at=QUEUED_AT,
        )
        .start_processing(at=STARTED_AT)
        .require_review(at=REVIEWED_AT)
    )


def review_required_run() -> ProcessingRun:
    return (
        ProcessingRun.queue(run_id=RUN_ID, document_id=DOCUMENT_ID, queued_at=QUEUED_AT)
        .start(at=STARTED_AT)
        .require_review(at=REVIEWED_AT)
    )


def complete_invoice_extraction() -> InvoiceExtraction:
    return InvoiceExtraction(
        processing_run_id=RUN_ID,
        method=InvoiceExtractionMethod.DETERMINISTIC_RULES,
        invoice_number="INV-2026-001",
        issue_date=date(2026, 9, 17),
        supplier_name="Acme Supplies Ltd",
        currency="EUR",
        total_amount=Decimal("149.99"),
        extracted_at=REVIEWED_AT,
    )


@pytest.mark.anyio
async def test_approves_a_review_required_document_with_authenticated_operator(
    migrated_postgres_url: str,
    tmp_path: Path,
) -> None:
    settings = Settings(
        environment="test",
        database_url=PostgresDsn(migrated_postgres_url),
        storage_root=tmp_path / "data",
        review_operator_token=SecretStr(TOKEN),
        review_operator_id="operator-42",
    )
    application = create_app(settings)
    database = cast(Database, application.state.database)
    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(review_required_document())
            await SqlAlchemyProcessingRunRepository(session).add(review_required_run())
            await SqlAlchemyInvoiceExtractionRepository(session).add(complete_invoice_extraction())

        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            invalid_response = await client.post(
                f"/api/v1/documents/{DOCUMENT_ID}/review-resolution",
                headers={"Authorization": f"Bearer {TOKEN}"},
                json={"decision": "APPROVE", "review_note": "   "},
            )
            response = await client.post(
                f"/api/v1/documents/{DOCUMENT_ID}/review-resolution",
                headers={"Authorization": f"Bearer {TOKEN}"},
                json={
                    "decision": "APPROVE",
                    "review_note": "Matched the supplier statement.",
                    "corrections": [
                        {"field": "TOTAL_AMOUNT", "corrected_value": "159.99"},
                    ],
                },
            )
            status_response = await client.get(f"/api/v1/documents/{DOCUMENT_ID}")
    finally:
        await database.dispose()

    assert response.status_code == 200
    assert invalid_response.status_code == 422
    assert invalid_response.json()["type"] == "urn:problem:invalid-review-resolution"
    assert response.json()["decision"] == "APPROVE"
    assert response.json()["reviewer_id"] == "operator-42"
    assert response.json()["replayed"] is False
    assert status_response.json()["status"] == "APPROVED"
    assert status_response.json()["current_run"]["status"] == "COMPLETED"
    assert status_response.json()["current_run"]["review_resolution"] == {
        "decision": "APPROVE",
        "reviewer_id": "operator-42",
        "review_note": "Matched the supplier statement.",
        "resolved_at": response.json()["resolved_at"],
        "corrections": [
            {
                "field": "TOTAL_AMOUNT",
                "corrected_value": "159.9900",
                "source": "MANUAL",
                "corrected_at": response.json()["resolved_at"],
            }
        ],
    }


@pytest.mark.anyio
async def test_rejects_unauthenticated_review_resolution(
    migrated_postgres_url: str,
    tmp_path: Path,
) -> None:
    settings = Settings(
        environment="test",
        database_url=PostgresDsn(migrated_postgres_url),
        storage_root=tmp_path / "data",
        review_operator_token=SecretStr(TOKEN),
    )
    application = create_app(settings)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/api/v1/documents/{DOCUMENT_ID}/review-resolution",
                json={"decision": "REJECT"},
            )
    finally:
        await cast(Database, application.state.database).dispose()

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["type"] == "urn:problem:review-authentication-rejected"


def test_exposes_a_stable_review_resolution_contract() -> None:
    application = create_app(Settings(environment="test"))
    operation = application.openapi()["paths"]["/api/v1/documents/{document_id}/review-resolution"][
        "post"
    ]

    assert operation["operationId"] == "resolveDocumentReview"
    assert operation["tags"] == ["Documents"]
    assert set(operation["responses"]) >= {"200", "401", "404", "409", "422", "503"}
    assert set(operation["responses"]["401"]["content"]) == {"application/problem+json"}
