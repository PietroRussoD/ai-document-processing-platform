"""Tests for the isolated local Ollama invoice-extraction client."""

import json

import pytest

from document_platform.adapters.outbound.ollama import (
    OllamaInvoiceExtractionClient,
    OllamaInvoiceExtractionError,
    OllamaInvoiceExtractionSettings,
)


def test_extracts_valid_structured_invoice_fields() -> None:
    received: list[tuple[str, dict[str, object], float]] = []

    def post_json(
        url: str, payload: dict[str, object], timeout_seconds: float
    ) -> dict[str, object]:
        received.append((url, payload, timeout_seconds))
        return response(
            invoice_number=" INV-42 ",
            issue_date="2026-09-19",
            supplier_name="Supplier Ltd",
            currency="EUR",
            total_amount="12.50",
        )

    client = OllamaInvoiceExtractionClient(
        settings=OllamaInvoiceExtractionSettings(
            base_url="http://ollama.local/",
            model="invoice-model",
            timeout_seconds=12.5,
        ),
        post_json=post_json,
    )

    fields = client.extract("Invoice INV-42")

    assert fields.invoice_number == "INV-42"
    assert fields.total_amount == "12.50"
    assert received[0][0] == "http://ollama.local/api/chat"
    assert received[0][2] == 12.5
    assert received[0][1]["model"] == "invoice-model"
    assert received[0][1]["stream"] is False
    assert received[0][1]["think"] is False
    assert received[0][1]["options"] == {"temperature": 0}
    response_schema = received[0][1]["format"]
    assert isinstance(response_schema, dict)
    assert response_schema["required"] == [
        "invoice_number",
        "issue_date",
        "supplier_name",
        "currency",
        "total_amount",
    ]


def test_rejects_a_response_that_does_not_match_the_schema() -> None:
    client = OllamaInvoiceExtractionClient(
        settings=OllamaInvoiceExtractionSettings(
            base_url="http://ollama.local",
            model="invoice-model",
        ),
        post_json=lambda _url, _payload, _timeout: response(invoice_number="INV-42"),
    )

    with pytest.raises(OllamaInvoiceExtractionError, match="invalid structured response"):
        client.extract("Invoice INV-42")


def test_rejects_a_response_without_message_content() -> None:
    client = OllamaInvoiceExtractionClient(
        settings=OllamaInvoiceExtractionSettings(
            base_url="http://ollama.local",
            model="invoice-model",
        ),
        post_json=lambda _url, _payload, _timeout: {"message": {}},
    )

    with pytest.raises(OllamaInvoiceExtractionError, match="message content"):
        client.extract("Invoice INV-42")


def test_rejects_blank_extraction_text() -> None:
    client = OllamaInvoiceExtractionClient(
        settings=OllamaInvoiceExtractionSettings(
            base_url="http://ollama.local",
            model="invoice-model",
        ),
        post_json=lambda _url, _payload, _timeout: {},
    )

    with pytest.raises(ValueError, match="text must not be blank"):
        client.extract("  ")


def response(**fields: str | None) -> dict[str, object]:
    return {"message": {"content": json.dumps(fields)}}
