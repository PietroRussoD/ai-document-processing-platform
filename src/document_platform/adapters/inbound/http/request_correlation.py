"""Bounded request correlation for the HTTP adapter."""

import re
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from uuid import uuid4

from fastapi import Request, Response

CORRELATION_ID_HEADER = "X-Correlation-ID"
_SAFE_CORRELATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def current_correlation_id() -> str | None:
    return _correlation_id.get()


async def correlate_request(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    correlation_id = _validated_correlation_id(request.headers.get(CORRELATION_ID_HEADER))
    token = _correlation_id.set(correlation_id)
    try:
        response = await call_next(request)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response
    finally:
        _correlation_id.reset(token)


def _validated_correlation_id(candidate: str | None) -> str:
    if candidate is not None and _SAFE_CORRELATION_ID.fullmatch(candidate):
        return candidate
    return str(uuid4())
