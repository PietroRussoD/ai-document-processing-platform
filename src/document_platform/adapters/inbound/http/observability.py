"""Prometheus exposition and request instrumentation for the HTTP adapter."""

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from time import perf_counter

from fastapi import APIRouter, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)

from document_platform.adapters.inbound.http.request_correlation import current_correlation_id
from document_platform.application.ports import ProcessingRunMetricsSnapshot
from document_platform.domain.processing import ProcessingRunStatus

logger = logging.getLogger(__name__)


class HttpMetrics:
    def __init__(self, *, application_version: str) -> None:
        self.registry = CollectorRegistry(auto_describe=True)
        build_info = Info(
            "document_platform_build",
            "Build information for the document-processing API.",
            registry=self.registry,
        )
        build_info.info({"version": application_version})
        self._request_count = Counter(
            "document_platform_http_requests",
            "Completed HTTP requests handled by the document-processing API.",
            ("method", "route", "status_class"),
            registry=self.registry,
        )
        self._request_duration = Histogram(
            "document_platform_http_request_duration_seconds",
            "HTTP request duration handled by the document-processing API.",
            ("method", "route"),
            registry=self.registry,
        )
        self._processing_run_count = Gauge(
            "document_platform_processing_runs",
            "Durable processing runs grouped by their current status.",
            ("status",),
            registry=self.registry,
        )
        self._oldest_queued_age = Gauge(
            "document_platform_processing_queue_oldest_age_seconds",
            "Age in seconds of the oldest queued processing run.",
            registry=self.registry,
        )

    def observe(self, *, request: Request, response: Response, duration_seconds: float) -> None:
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        self._request_count.labels(
            method=request.method,
            route=route_path,
            status_class=f"{response.status_code // 100}xx",
        ).inc()
        self._request_duration.labels(
            method=request.method,
            route=route_path,
        ).observe(duration_seconds)

    def observe_processing_runs(
        self,
        *,
        snapshot: ProcessingRunMetricsSnapshot,
        observed_at: datetime,
    ) -> None:
        for status in ProcessingRunStatus:
            self._processing_run_count.labels(status=status).set(
                snapshot.counts_by_status.get(status, 0)
            )
        oldest_queued_at = snapshot.oldest_queued_at
        if oldest_queued_at is None:
            self._oldest_queued_age.set(0)
            return
        self._oldest_queued_age.set(max(0, (observed_at - oldest_queued_at).total_seconds()))


router = APIRouter(tags=["Observability"])


@router.get("/metrics", include_in_schema=False)
async def get_metrics(request: Request) -> Response:
    metrics = request.app.state.http_metrics
    snapshot = await request.app.state.processing_run_metrics_reader.read()
    metrics.observe_processing_runs(snapshot=snapshot, observed_at=datetime.now(UTC))
    return Response(content=generate_latest(metrics.registry), media_type=CONTENT_TYPE_LATEST)


async def observe_request(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    started_at = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "HTTP request failed",
            extra={
                "event": "http_request_failed",
                "correlation_id": current_correlation_id(),
                "http_method": request.method,
                "http_route": _route_template(request),
                "http_status": 500,
                "duration_seconds": perf_counter() - started_at,
            },
        )
        raise
    duration_seconds = perf_counter() - started_at
    request.app.state.http_metrics.observe(
        request=request,
        response=response,
        duration_seconds=duration_seconds,
    )
    logger.info(
        "HTTP request completed",
        extra={
            "event": "http_request_completed",
            "correlation_id": current_correlation_id(),
            "http_method": request.method,
            "http_route": _route_template(request),
            "http_status": response.status_code,
            "duration_seconds": duration_seconds,
        },
    )
    return response


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", "unmatched")
