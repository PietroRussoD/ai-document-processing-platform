"""Liveness endpoint integration tests."""

from typing import TypedDict, cast

import pytest
from httpx import ASGITransport, AsyncClient

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


def test_exposes_a_stable_openapi_operation() -> None:
    application = create_app(Settings(environment="test"))

    openapi = cast(OpenApiDocument, application.openapi())
    operation = openapi["paths"]["/health/live"]["get"]

    assert operation["operationId"] == "getLiveness"
    assert operation["tags"] == ["Health"]
