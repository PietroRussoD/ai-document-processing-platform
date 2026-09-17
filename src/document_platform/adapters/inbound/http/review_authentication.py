"""Local bearer-token authentication for manual review operations."""

from dataclasses import dataclass
from secrets import compare_digest

from document_platform.settings import Settings


@dataclass(frozen=True, slots=True)
class AuthenticatedReviewOperator:
    reviewer_id: str


class ReviewAuthenticationUnavailable(RuntimeError):
    """Raised when review authentication is not configured."""


class ReviewAuthenticationRejected(RuntimeError):
    """Raised when a caller does not present the configured bearer token."""


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
