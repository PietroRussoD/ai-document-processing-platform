"""Structured logging configuration tests."""

import json
import logging

from document_platform.logging_configuration import JsonLogFormatter


def test_formats_only_safe_structured_fields_with_request_correlation() -> None:
    formatter = JsonLogFormatter(
        service="test-service",
        component="api",
        correlation_id_provider=lambda: "request-42",
    )
    record = logging.LogRecord(
        name="document_platform.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=20,
        msg="HTTP request completed",
        args=(),
        exc_info=None,
    )
    record.event = "http_request_completed"
    record.http_method = "GET"
    record.http_route = "/api/v1/documents/{document_id}"
    record.http_status = 200
    record.secret = "must-not-be-serialized"

    payload = json.loads(formatter.format(record))

    assert payload["service"] == "test-service"
    assert payload["component"] == "api"
    assert payload["event"] == "http_request_completed"
    assert payload["correlation_id"] == "request-42"
    assert payload["http_route"] == "/api/v1/documents/{document_id}"
    assert payload["http_status"] == 200
    assert "secret" not in payload
