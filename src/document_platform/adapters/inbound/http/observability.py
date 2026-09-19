"""Prometheus exposition and request instrumentation for the HTTP adapter."""

from collections.abc import Awaitable, Callable
from time import perf_counter

from fastapi import APIRouter, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    Info,
    generate_latest,
)


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


router = APIRouter(tags=["Observability"])


@router.get("/metrics", include_in_schema=False)
async def get_metrics(request: Request) -> Response:
    metrics = request.app.state.http_metrics
    return Response(content=generate_latest(metrics.registry), media_type=CONTENT_TYPE_LATEST)


async def observe_request(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    started_at = perf_counter()
    response = await call_next(request)
    request.app.state.http_metrics.observe(
        request=request,
        response=response,
        duration_seconds=perf_counter() - started_at,
    )
    return response
