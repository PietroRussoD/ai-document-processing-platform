"""Prometheus HTTP exposition integration tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from document_platform.bootstrap import create_app
from document_platform.settings import Settings


@pytest.mark.anyio
async def test_exposes_build_and_route_metrics_without_request_identifiers() -> None:
    application = create_app(Settings(environment="test"))
    transport = ASGITransport(app=application)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health_response = await client.get("/health/live")
        metrics_response = await client.get("/metrics")

    assert health_response.status_code == 200
    assert metrics_response.status_code == 200
    assert metrics_response.headers["content-type"].startswith("text/plain")
    assert 'document_platform_build_info{version="0.5.0.dev0"} 1.0' in (metrics_response.text)
    assert (
        "document_platform_http_requests_total"
        '{method="GET",route="/health/live",status_class="2xx"} 1.0' in metrics_response.text
    )
    assert (
        "document_platform_http_requests_total"
        '{method="GET",route="/metrics",status_class="2xx"}' not in metrics_response.text
    )
    assert "http://test" not in metrics_response.text
