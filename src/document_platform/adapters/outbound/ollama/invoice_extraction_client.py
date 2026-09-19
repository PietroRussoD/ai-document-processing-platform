"""Structured local Ollama client for the invoice-extraction evaluation spike."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, ValidationError

from document_platform.evaluation import InvoiceFields

type JsonPost = Callable[[str, dict[str, object], float], dict[str, object]]


class OllamaInvoiceExtractionError(RuntimeError):
    """Raised when Ollama cannot return a valid structured invoice response."""


@dataclass(frozen=True, slots=True)
class OllamaInvoiceExtractionSettings:
    base_url: str
    model: str
    timeout_seconds: float = 60.0

    def __post_init__(self) -> None:
        if not self.base_url.strip():
            raise ValueError("base_url must not be blank")
        if not self.model.strip():
            raise ValueError("model must not be blank")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


class _OllamaInvoiceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice_number: str | None
    issue_date: str | None
    supplier_name: str | None
    currency: str | None
    total_amount: str | None


class OllamaInvoiceExtractionClient:
    """Call Ollama's structured-output API without joining the production workflow."""

    def __init__(
        self,
        *,
        settings: OllamaInvoiceExtractionSettings,
        post_json: JsonPost | None = None,
    ) -> None:
        self._settings = settings
        self._post_json = post_json or _post_json

    def extract(self, text: str) -> InvoiceFields:
        if not text.strip():
            raise ValueError("text must not be blank")
        response = self._post_json(
            f"{self._settings.base_url.rstrip('/')}/api/chat",
            {
                "model": self._settings.model,
                "stream": False,
                "format": _OllamaInvoiceResponse.model_json_schema(),
                "options": {"temperature": 0},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Extract invoice fields from the supplied text. Return only the JSON "
                            "object defined by the response schema. Use null when a field is "
                            "absent. Keep total_amount as a decimal string and currency as an "
                            "ISO 4217 code."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
            },
            self._settings.timeout_seconds,
        )
        content = _response_content(response)
        try:
            parsed = _OllamaInvoiceResponse.model_validate_json(content)
        except ValidationError as error:
            raise OllamaInvoiceExtractionError(
                "Ollama returned an invalid structured response"
            ) from error
        return InvoiceFields(
            invoice_number=_strip_or_none(parsed.invoice_number),
            issue_date=_strip_or_none(parsed.issue_date),
            supplier_name=_strip_or_none(parsed.supplier_name),
            currency=_strip_or_none(parsed.currency),
            total_amount=_strip_or_none(parsed.total_amount),
        )


def _post_json(url: str, payload: dict[str, object], timeout_seconds: float) -> dict[str, object]:
    request = Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            parsed = json.loads(response.read().decode("utf-8"))
    except (HTTPError, OSError, URLError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OllamaInvoiceExtractionError("Ollama request failed") from error
    if not isinstance(parsed, dict):
        raise OllamaInvoiceExtractionError("Ollama returned a non-object response")
    return cast(dict[str, object], parsed)


def _response_content(response: dict[str, object]) -> str:
    message = response.get("message")
    if not isinstance(message, dict):
        raise OllamaInvoiceExtractionError("Ollama response did not contain a message object")
    content = cast(dict[str, object], message).get("content")
    if not isinstance(content, str):
        raise OllamaInvoiceExtractionError("Ollama response did not contain message content")
    return content


def _strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
