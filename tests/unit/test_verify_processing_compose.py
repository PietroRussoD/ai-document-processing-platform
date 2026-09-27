"""Focused tests for the local Compose smoke command."""

from typing import cast
from uuid import UUID

import httpx
import pymupdf
import pytest

from scripts.verify_processing_compose import (
    SmokeTestError,
    document_console_url,
    synthetic_invoice_pdf,
    verify_processing,
)


def test_synthetic_invoice_is_a_readable_pdf() -> None:
    document = pymupdf.open(stream=synthetic_invoice_pdf(), filetype="pdf")
    try:
        text = cast(str, document[0].get_text())  # pyright: ignore[reportUnknownMemberType]
        assert "Supplier: Example Ltd" in text
    finally:
        document.close()


def test_console_link_opens_the_verified_document() -> None:
    document_id = "00000000-0000-4000-8000-000000000001"
    url = httpx.URL(document_console_url("http://127.0.0.1:18088/", UUID(document_id)))

    assert url.path == "/"
    assert url.params["documentId"] == document_id
    assert url.port == 18088


def test_verifies_upload_and_processing_through_console() -> None:
    statuses = iter(["UPLOADED", "REVIEW_REQUIRED"])

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, text="<title>Document Processing Console</title>")
        if request.method == "POST":
            assert request.url.path == "/api/v1/documents"
            assert request.headers["Idempotency-Key"].startswith("compose-smoke-")
            assert b"%PDF-" in request.content
            return httpx.Response(202, json={"document_id": "00000000-0000-4000-8000-000000000001"})
        status = next(statuses)
        return httpx.Response(
            200,
            json={
                "status": status,
                "current_run": {
                    "status": status,
                    "processing_output": {
                        "embedded_text": {"method": "PYMUPDF"},
                        "classification": {"document_type": "INVOICE"},
                    },
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond), base_url="http://test") as client:
        document_id = verify_processing(client, timeout_seconds=1.0, poll_interval_seconds=0)

    assert str(document_id) == "00000000-0000-4000-8000-000000000001"


def test_rejects_a_terminal_failure() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, text="Document Processing Console")
        if request.method == "POST":
            return httpx.Response(202, json={"document_id": "00000000-0000-4000-8000-000000000001"})
        return httpx.Response(200, json={"status": "FAILED"})

    with (
        httpx.Client(transport=httpx.MockTransport(respond), base_url="http://test") as client,
        pytest.raises(SmokeTestError, match="unexpected terminal status FAILED"),
    ):
        verify_processing(client, timeout_seconds=1.0)


def test_times_out_when_processing_does_not_advance() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, text="Document Processing Console")
        if request.method == "POST":
            return httpx.Response(202, json={"document_id": "00000000-0000-4000-8000-000000000001"})
        return httpx.Response(200, json={"status": "UPLOADED"})

    with (
        httpx.Client(transport=httpx.MockTransport(respond), base_url="http://test") as client,
        pytest.raises(SmokeTestError, match="past the timeout"),
    ):
        verify_processing(client, timeout_seconds=0)
