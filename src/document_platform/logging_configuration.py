"""Process-wide JSON logging with an explicit safe field allowlist."""

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime

type CorrelationIdProvider = Callable[[], str | None]

_STRUCTURED_FIELDS = (
    "event",
    "correlation_id",
    "http_method",
    "http_route",
    "http_status",
    "duration_seconds",
    "claimed_count",
    "dispatched_count",
    "deferred_count",
)


class JsonLogFormatter(logging.Formatter):
    def __init__(
        self,
        *,
        service: str,
        component: str,
        correlation_id_provider: CorrelationIdProvider | None = None,
    ) -> None:
        super().__init__()
        self._service = service
        self._component = component
        self._correlation_id_provider = correlation_id_provider or (lambda: None)

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "service": self._service,
            "component": self._component,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _STRUCTURED_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if "correlation_id" not in payload:
            correlation_id = self._correlation_id_provider()
            if correlation_id is not None:
                payload["correlation_id"] = correlation_id

        if record.exc_info is not None:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def configure_json_logging(
    *,
    level: str,
    component: str,
    correlation_id_provider: CorrelationIdProvider | None = None,
) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        JsonLogFormatter(
            service="ai-document-processing-platform",
            component=component,
            correlation_id_provider=correlation_id_provider,
        )
    )
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)
