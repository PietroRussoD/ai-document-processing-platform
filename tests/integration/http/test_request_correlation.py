"""HTTP request-correlation integration tests."""

from typing import cast
from unittest.mock import patch
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient, Response

from document_platform.adapters.inbound.http import observability
from document_platform.adapters.inbound.http.request_correlation import CORRELATION_ID_HEADER
from document_platform.bootstrap import create_app
from document_platform.settings import Settings


@pytest.mark.anyio
async def test_preserves_a_safe_client_correlation_id() -> None:
    response = await _get_liveness({CORRELATION_ID_HEADER: "client-request_42"})

    assert response.status_code == 200
    assert response.headers[CORRELATION_ID_HEADER] == "client-request_42"


@pytest.mark.anyio
async def test_adds_the_effective_correlation_id_to_the_request_log() -> None:
    with patch.object(observability.logger, "info") as log_info:
        await _get_liveness({CORRELATION_ID_HEADER: "client-request_42"})

    log_info.assert_called_once()
    fields = cast(dict[str, object], log_info.call_args.kwargs["extra"])
    assert fields["event"] == "http_request_completed"
    assert fields["correlation_id"] == "client-request_42"
    assert fields["http_route"] == "/health/live"


@pytest.mark.anyio
@pytest.mark.parametrize("candidate", [None, "", "contains spaces", "contains/slash", "x" * 129])
async def test_generates_a_correlation_id_when_the_client_value_is_unsafe(
    candidate: str | None,
) -> None:
    headers = {} if candidate is None else {CORRELATION_ID_HEADER: candidate}

    response = await _get_liveness(headers)

    assert response.status_code == 200
    UUID(response.headers[CORRELATION_ID_HEADER])


async def _get_liveness(headers: dict[str, str]) -> Response:
    application = create_app(Settings(environment="test"))
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/health/live", headers=headers)
