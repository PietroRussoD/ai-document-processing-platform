"""Local bearer-token authentication for document operator operations."""

from dataclasses import dataclass
from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import RequestResponseEndpoint

from document_platform.settings import Settings


@dataclass(frozen=True, slots=True)
class AuthenticatedReviewOperator:
    reviewer_id: str


class ReviewAuthenticationUnavailable(RuntimeError):
    """Raised when review authentication is not configured."""


class ReviewAuthenticationRejected(RuntimeError):
    """Raised when a caller does not present the configured bearer token."""


_bearer_scheme = HTTPBearer(auto_error=False, scheme_name="OperatorBearer")


def authenticate_review_operator(
    *,
    authorization: str | None,
    settings: Settings,
) -> AuthenticatedReviewOperator:
    expected_token = settings.review_operator_token
    if expected_token is None:
        raise ReviewAuthenticationUnavailable("review authentication is not configured")

    supplied_token = _parse_bearer_token(authorization)
    if supplied_token is None or not compare_digest(
        supplied_token,
        expected_token.get_secret_value(),
    ):
        raise ReviewAuthenticationRejected("review authentication was rejected")
    return AuthenticatedReviewOperator(reviewer_id=settings.review_operator_id)


def _parse_bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or separator != " " or not token or " " in token:
        return None
    return token


def require_document_operator(
    request: Request,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> AuthenticatedReviewOperator:
    authorization = (
        None if credentials is None else f"{credentials.scheme} {credentials.credentials}"
    )
    return authenticate_review_operator(
        authorization=authorization,
        settings=request.app.state.settings,
    )


DocumentOperator = Annotated[
    AuthenticatedReviewOperator,
    Depends(require_document_operator),
]


async def authenticate_document_api_request(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    if request.url.path != "/api/v1/documents" and not request.url.path.startswith(
        "/api/v1/documents/"
    ):
        return await call_next(request)

    authorization = request.headers.get("Authorization")
    try:
        authenticate_review_operator(
            authorization=authorization,
            settings=request.app.state.settings,
        )
    except (ReviewAuthenticationRejected, ReviewAuthenticationUnavailable) as error:
        from document_platform.adapters.inbound.http.problems import (
            expected_failure_handler,
        )

        return await expected_failure_handler(request, error)

    return await call_next(request)
