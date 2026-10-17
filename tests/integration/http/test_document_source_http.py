"""HTTP integration tests for authenticated source-document retrieval."""

from hashlib import sha256
from pathlib import Path
from typing import cast
from uuid import UUID

import pymupdf
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import PostgresDsn, SecretStr

from document_platform.adapters.outbound.postgresql.database import Database
from document_platform.bootstrap import create_app
from document_platform.settings import Settings

TOKEN = "review-operator-token-with-at-least-thirty-two-characters"
UNKNOWN_DOCUMENT_ID = UUID("d0d0d0d0-d0d0-40d0-80d0-d0d0d0d0d0d0")


def _pdf_bytes() -> bytes:
    document = pymupdf.open()
    try:
        document.new_page()
        return document.tobytes()  # pyright: ignore[reportUnknownMemberType]
    finally:
        document.close()


@pytest.mark.anyio
async def test_retrieves_pdf_only_after_authenticating_and_hides_storage_details(
    migrated_postgres_url: str,
    tmp_path: Path,
) -> None:
    storage_root = tmp_path / "data"
    application = create_app(
        Settings(
            environment="test",
            database_url=PostgresDsn(migrated_postgres_url),
            storage_root=storage_root,
            review_operator_token=SecretStr(TOKEN),
        )
    )
    database = cast(Database, application.state.database)
    content = _pdf_bytes()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            upload = await client.post(
                "/api/v1/documents",
                headers={
                    "Authorization": f"Bearer {TOKEN}",
                    "Idempotency-Key": "document-source-http-test",
                },
                files={"document": ("private-name.pdf", content, "application/pdf")},
            )
            document_id = upload.json()["document_id"]
            digest = sha256(content).hexdigest()
            source_url = f"/api/v1/documents/{document_id}/source"
            unauthenticated = await client.get(source_url)
            unauthenticated_unknown = await client.get(
                f"/api/v1/documents/{UNKNOWN_DOCUMENT_ID}/source"
            )
            missing = await client.get(
                f"/api/v1/documents/{UNKNOWN_DOCUMENT_ID}/source",
                headers={"Authorization": f"Bearer {TOKEN}"},
            )
            preview = await client.get(
                source_url,
                headers={"Authorization": f"Bearer {TOKEN}"},
            )

            blob_path = storage_root / "blobs" / "sha256" / digest[:2] / digest
            blob_path.unlink()
            unavailable = await client.get(
                source_url,
                headers={"Authorization": f"Bearer {TOKEN}"},
            )
    finally:
        await database.dispose()

    assert upload.status_code == 202
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["type"] == "urn:problem:operator-authentication-rejected"
    assert unauthenticated_unknown.status_code == 401
    assert missing.status_code == 404
    assert missing.json()["type"] == "urn:problem:document-not-found"
    assert preview.status_code == 200
    assert preview.content == content
    assert preview.headers["content-type"] == "application/pdf"
    assert preview.headers["content-disposition"] == 'inline; filename="document.pdf"'
    assert preview.headers["cache-control"] == "no-store"
    assert preview.headers["x-content-type-options"] == "nosniff"
    assert "private-name.pdf" not in preview.headers["content-disposition"]
    assert unavailable.status_code == 503
    assert unavailable.json()["type"] == "urn:problem:source-document-unavailable"
    assert digest not in unavailable.text


def test_exposes_source_as_a_binary_pdf_contract() -> None:
    application = create_app(Settings(environment="test"))
    operation = application.openapi()["paths"]["/api/v1/documents/{document_id}/source"]["get"]

    assert operation["operationId"] == "getDocumentSource"
    assert operation["responses"]["200"]["content"]["application/pdf"]["schema"] == {
        "type": "string",
        "format": "binary",
    }
    assert set(operation["responses"]) >= {"200", "401", "404", "503"}
    assert any(
        parameter["name"].casefold() == "authorization" and parameter["in"] == "header"
        for parameter in operation["parameters"]
    )
