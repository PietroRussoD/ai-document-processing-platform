"""Document-upload HTTP integration tests."""

from hashlib import sha256
from pathlib import Path
from typing import TypedDict, cast

import pymupdf
import pytest
from httpx import ASGITransport, AsyncClient, Response
from pydantic import PostgresDsn
from sqlalchemy import text

from document_platform.adapters.outbound.postgresql.database import Database
from document_platform.bootstrap import create_app
from document_platform.settings import Settings


class AcceptedDocumentBody(TypedDict):
    document_id: str
    processing_run_id: str
    accepted_at: str
    replayed: bool


def _pdf_bytes() -> bytes:
    document = pymupdf.open()
    document.new_page()
    content = document.tobytes()  # pyright: ignore[reportUnknownMemberType]
    document.close()
    return content


async def _post_document(
    client: AsyncClient,
    *,
    content: bytes,
    media_type: str = "application/pdf",
    include_idempotency_key: bool = True,
) -> Response:
    headers = {"Idempotency-Key": "http-upload-test"} if include_idempotency_key else {}
    return await client.post(
        "/api/v1/documents",
        headers=headers,
        files={"document": ("supplier-invoice.pdf", content, media_type)},
    )


@pytest.mark.anyio
async def test_accepts_and_replays_a_pdf_upload(
    migrated_postgres_url: str,
    tmp_path: Path,
) -> None:
    application = create_app(
        Settings(
            environment="test",
            database_url=PostgresDsn(migrated_postgres_url),
            storage_root=tmp_path / "data",
        )
    )
    database = cast(Database, application.state.database)
    transport = ASGITransport(app=application)
    content = _pdf_bytes()

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first_response = await _post_document(client, content=content)
            replay_response = await _post_document(client, content=content)
            first = cast(AcceptedDocumentBody, first_response.json())
            status_response = await client.get(f"/api/v1/documents/{first['document_id']}")

        replay = cast(AcceptedDocumentBody, replay_response.json())
        async with database.sessions() as session:
            counts = await session.execute(
                text(
                    """
                    SELECT
                        (SELECT count(*) FROM documents WHERE id = :document_id),
                        (SELECT count(*) FROM processing_runs WHERE id = :processing_run_id),
                        (SELECT count(*) FROM upload_idempotency_records
                         WHERE idempotency_key = 'http-upload-test'),
                        (SELECT count(*) FROM workflow_start_requests
                         WHERE processing_run_id = :processing_run_id)
                    """
                ),
                {
                    "document_id": first["document_id"],
                    "processing_run_id": first["processing_run_id"],
                },
            )
            persisted_counts = counts.one()
    finally:
        await database.dispose()

    assert first_response.status_code == 202
    assert first["replayed"] is False
    assert replay_response.status_code == 202
    assert replay["replayed"] is True
    assert replay["document_id"] == first["document_id"]
    assert replay["processing_run_id"] == first["processing_run_id"]
    assert status_response.status_code == 200
    assert status_response.json() == {
        "id": first["document_id"],
        "original_filename": "supplier-invoice.pdf",
        "media_type": "application/pdf",
        "size_bytes": len(content),
        "page_count": 1,
        "content_sha256": sha256(content).hexdigest(),
        "status": "UPLOADED",
        "accepted_at": first["accepted_at"],
        "status_changed_at": first["accepted_at"],
        "current_run": {
            "id": first["processing_run_id"],
            "status": "QUEUED",
            "queued_at": first["accepted_at"],
            "started_at": None,
            "status_changed_at": first["accepted_at"],
            "finished_at": None,
            "attempt_count": 0,
        },
    }
    assert "storage_key" not in status_response.json()
    assert persisted_counts == (1, 1, 1, 1)
    assert (
        len([path for path in tmp_path.joinpath("data", "blobs").rglob("*") if path.is_file()]) == 1
    )
    incoming_directory = tmp_path / "data" / "incoming"
    assert not incoming_directory.exists() or list(incoming_directory.iterdir()) == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("content", "media_type", "expected_status", "expected_type"),
    [
        (b"plain text", "text/plain", 415, "urn:problem:unsupported-media-type"),
        (b"too large", "application/pdf", 413, "urn:problem:document-too-large"),
    ],
)
async def test_rejects_an_unsupported_or_oversized_upload(
    migrated_postgres_url: str,
    tmp_path: Path,
    content: bytes,
    media_type: str,
    expected_status: int,
    expected_type: str,
) -> None:
    application = create_app(
        Settings(
            environment="test",
            database_url=PostgresDsn(migrated_postgres_url),
            storage_root=tmp_path / "data",
            max_document_bytes=5,
        )
    )
    database = cast(Database, application.state.database)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=application),
            base_url="http://test",
        ) as client:
            response = await _post_document(client, content=content, media_type=media_type)
    finally:
        await database.dispose()

    assert response.status_code == expected_status
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"] == expected_type
    incoming_directory = tmp_path / "data" / "incoming"
    assert not incoming_directory.exists() or list(incoming_directory.iterdir()) == []
    assert not tmp_path.joinpath("data", "blobs").exists()


@pytest.mark.anyio
async def test_maps_missing_request_fields_to_problem_details(
    migrated_postgres_url: str,
    tmp_path: Path,
) -> None:
    application = create_app(
        Settings(
            environment="test",
            database_url=PostgresDsn(migrated_postgres_url),
            storage_root=tmp_path / "data",
        )
    )
    database = cast(Database, application.state.database)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=application),
            base_url="http://test",
        ) as client:
            response = await _post_document(
                client,
                content=_pdf_bytes(),
                include_idempotency_key=False,
            )
    finally:
        await database.dispose()

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "urn:problem:request-validation",
        "title": "Request validation failed",
        "status": 422,
        "detail": "The request does not satisfy the API contract.",
    }


@pytest.mark.anyio
async def test_returns_problem_details_for_an_unknown_document(
    migrated_postgres_url: str,
    tmp_path: Path,
) -> None:
    application = create_app(
        Settings(
            environment="test",
            database_url=PostgresDsn(migrated_postgres_url),
            storage_root=tmp_path / "data",
        )
    )
    database = cast(Database, application.state.database)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=application),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/documents/77777777-7777-4777-8777-777777777777")
    finally:
        await database.dispose()

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "urn:problem:document-not-found",
        "title": "Document not found",
        "status": 404,
        "detail": "document not found: 77777777-7777-4777-8777-777777777777",
    }


def test_exposes_a_stable_document_upload_contract() -> None:
    application = create_app(Settings(environment="test"))
    openapi = application.openapi()

    operation = openapi["paths"]["/api/v1/documents"]["post"]

    assert operation["operationId"] == "acceptDocumentUpload"
    assert operation["tags"] == ["Documents"]
    assert set(operation["responses"]) >= {"202", "400", "409", "413", "415", "422"}
    assert set(operation["responses"]["422"]["content"]) == {"application/problem+json"}

    status_operation = openapi["paths"]["/api/v1/documents/{document_id}"]["get"]
    assert status_operation["operationId"] == "getDocumentStatus"
    assert status_operation["tags"] == ["Documents"]
    assert set(status_operation["responses"]) >= {"200", "404", "422"}
    assert set(status_operation["responses"]["404"]["content"]) == {"application/problem+json"}
