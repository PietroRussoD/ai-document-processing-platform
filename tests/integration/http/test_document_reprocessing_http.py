"""HTTP integration tests for controlled document reprocessing."""

from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import PostgresDsn, SecretStr

from document_platform.adapters.outbound.postgresql.database import Database
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyProcessingRunRepository,
)
from document_platform.bootstrap import create_app
from document_platform.domain.documents import Document
from document_platform.domain.processing import ProcessingRun
from document_platform.settings import Settings

TOKEN = "review-operator-token-with-at-least-thirty-two-characters"
DOCUMENT_ID = UUID("f8d8d8d8-d8d8-48d8-88d8-d8d8d8d8d8d8")
RUN_ID = UUID("f9d9d9d9-d9d9-49d9-89d9-d9d9d9d9d9d9")
QUEUED_AT = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)
STARTED_AT = datetime(2026, 9, 20, 10, 1, tzinfo=UTC)
COMPLETED_AT = datetime(2026, 9, 20, 10, 2, tzinfo=UTC)


def completed_document() -> Document:
    return (
        Document.accept_pdf(
            document_id=DOCUMENT_ID,
            original_filename="completed.pdf",
            size_bytes=10_000,
            page_count=1,
            content_sha256=DOCUMENT_ID.hex * 2,
            storage_key=f"blobs/{DOCUMENT_ID}",
            accepted_at=QUEUED_AT,
        )
        .start_processing(at=STARTED_AT)
        .approve(at=COMPLETED_AT)
    )


def completed_run() -> ProcessingRun:
    return (
        ProcessingRun.queue(run_id=RUN_ID, document_id=DOCUMENT_ID, queued_at=QUEUED_AT)
        .start(at=STARTED_AT)
        .complete(at=COMPLETED_AT)
    )


@pytest.mark.anyio
async def test_requests_and_replays_controlled_document_reprocessing(
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
            await SqlAlchemyDocumentRepository(session).add(completed_document())
            await SqlAlchemyProcessingRunRepository(session).add(completed_run())

        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            request_headers = {
                "Authorization": f"Bearer {TOKEN}",
                "Idempotency-Key": "reprocess-completed-document-001",
            }
            response = await client.post(
                f"/api/v1/documents/{DOCUMENT_ID}/reprocessing-requests",
                headers=request_headers,
                json={"reason": "Retry after the upstream OCR outage was resolved."},
            )
            replay_response = await client.post(
                f"/api/v1/documents/{DOCUMENT_ID}/reprocessing-requests",
                headers=request_headers,
                json={"reason": "Retry after the upstream OCR outage was resolved."},
            )
            status_response = await client.get(
                f"/api/v1/documents/{DOCUMENT_ID}",
                headers={"Authorization": f"Bearer {TOKEN}"},
            )
    finally:
        await database.dispose()

    assert response.status_code == 202
    assert response.json()["document_id"] == str(DOCUMENT_ID)
    assert response.json()["source_run_id"] == str(RUN_ID)
    assert response.json()["replayed"] is False
    assert replay_response.status_code == 202
    assert replay_response.json() == {**response.json(), "replayed": True}
    assert status_response.json()["status"] == "PROCESSING"
    assert status_response.json()["current_run"]["id"] == response.json()["replacement_run_id"]
    assert status_response.json()["current_run"]["previous_run_id"] == str(RUN_ID)
    assert status_response.json()["current_run"]["status"] == "QUEUED"


@pytest.mark.anyio
async def test_rejects_an_unauthenticated_reprocessing_request(
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
                f"/api/v1/documents/{DOCUMENT_ID}/reprocessing-requests",
                headers={"Idempotency-Key": "reprocess-unauthenticated-001"},
                json={"reason": "Retry after a recoverable failure."},
            )
    finally:
        await cast(Database, application.state.database).dispose()

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["type"] == "urn:problem:operator-authentication-rejected"


def test_exposes_a_stable_reprocessing_contract() -> None:
    application = create_app(Settings(environment="test"))
    operation = application.openapi()["paths"][
        "/api/v1/documents/{document_id}/reprocessing-requests"
    ]["post"]

    assert operation["operationId"] == "requestDocumentReprocessing"
    assert operation["tags"] == ["Documents"]
    assert set(operation["responses"]) >= {"202", "401", "404", "409", "422", "503"}
    assert set(operation["responses"]["401"]["content"]) == {"application/problem+json"}
