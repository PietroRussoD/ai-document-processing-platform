"""Prometheus HTTP exposition integration tests."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from document_platform.application.ports import ProcessingRunMetricsSnapshot
from document_platform.bootstrap import create_app
from document_platform.domain.processing import ProcessingRunStatus
from document_platform.settings import Settings


@dataclass(frozen=True, slots=True)
class StubProcessingRunMetricsReader:
    snapshot: ProcessingRunMetricsSnapshot

    async def read(self) -> ProcessingRunMetricsSnapshot:
        return self.snapshot


@pytest.mark.anyio
async def test_exposes_build_and_route_metrics_without_request_identifiers() -> None:
    application = create_app(
        Settings(environment="test"),
        StubProcessingRunMetricsReader(
            ProcessingRunMetricsSnapshot(
                counts_by_status={
                    ProcessingRunStatus.QUEUED: 2,
                    ProcessingRunStatus.COMPLETED: 3,
                },
                oldest_queued_at=datetime.now(UTC) - timedelta(minutes=5),
            )
        ),
    )
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
    assert 'document_platform_processing_runs{status="QUEUED"} 2.0' in metrics_response.text
    assert 'document_platform_processing_runs{status="COMPLETED"} 3.0' in metrics_response.text
    assert "document_platform_processing_queue_oldest_age_seconds" in metrics_response.text
    assert (
        "document_platform_http_requests_total"
        '{method="GET",route="/metrics",status_class="2xx"}' not in metrics_response.text
    )
    assert "http://test" not in metrics_response.text
