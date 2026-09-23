"""Liveness endpoint integration tests."""

from typing import TypedDict, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import PostgresDsn
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from document_platform.adapters.inbound.http.health import database_is_available
from document_platform.bootstrap import create_app
from document_platform.settings import Settings


class OpenApiOperation(TypedDict):
    operationId: str
    tags: list[str]


class OpenApiDocument(TypedDict):
    paths: dict[str, dict[str, OpenApiOperation]]


@pytest.mark.anyio
async def test_reports_that_the_process_is_live() -> None:
    application = create_app(Settings(environment="test"))
    transport = ASGITransport(app=application)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "UP"}


@pytest.mark.anyio
async def test_reports_readiness_when_postgresql_is_available(postgres_url: str) -> None:
    application = create_app(Settings(environment="test", database_url=PostgresDsn(postgres_url)))
    transport = ASGITransport(app=application)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/ready")
    finally:
        await application.state.database.dispose()

    assert response.status_code == 200
    assert response.json() == {"status": "UP", "database": "UP"}


@pytest.mark.anyio
async def test_reports_unready_without_exposing_database_errors() -> None:
    application = create_app(Settings(environment="test"))
    transport = ASGITransport(app=application)
    unavailable = AsyncMock(return_value=False)

    try:
        with patch(
            "document_platform.adapters.inbound.http.health.database_is_available",
            new=unavailable,
        ):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/health/ready")
    finally:
        await application.state.database.dispose()

    assert response.status_code == 503
    assert response.json() == {"status": "DOWN", "database": "DOWN"}
    assert "error" not in response.text


@pytest.mark.anyio
async def test_treats_database_errors_as_unavailable() -> None:
    engine = MagicMock(spec=AsyncEngine)
    engine.connect.return_value.__aenter__.side_effect = SQLAlchemyError(
        "sensitive connection detail"
    )

    assert await database_is_available(cast(AsyncEngine, engine)) is False


def test_exposes_a_stable_openapi_operation() -> None:
    application = create_app(Settings(environment="test"))

    openapi = cast(OpenApiDocument, application.openapi())
    operation = openapi["paths"]["/health/live"]["get"]
    readiness_operation = openapi["paths"]["/health/ready"]["get"]

    assert operation["operationId"] == "getLiveness"
    assert operation["tags"] == ["Health"]
    assert readiness_operation["operationId"] == "getReadiness"
    assert readiness_operation["tags"] == ["Health"]
