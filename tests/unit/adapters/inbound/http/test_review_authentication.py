"""Local review-authentication tests."""

import pytest
from pydantic import SecretStr, ValidationError

from document_platform.adapters.inbound.http.review_authentication import (
    ReviewAuthenticationRejected,
    ReviewAuthenticationUnavailable,
    authenticate_review_operator,
)
from document_platform.settings import Settings

TOKEN = "review-operator-token-with-at-least-thirty-two-characters"


def configured_settings() -> Settings:
    return Settings(review_operator_token=SecretStr(TOKEN), review_operator_id="operator-42")


def test_authenticates_the_configured_bearer_token() -> None:
    operator = authenticate_review_operator(
        authorization=f"Bearer {TOKEN}",
        settings=configured_settings(),
    )

    assert operator.reviewer_id == "operator-42"


@pytest.mark.parametrize(
    "authorization",
    [None, "Basic credentials", "Bearer", "Bearer wrong-token", f"Token {TOKEN}"],
)
def test_rejects_missing_malformed_and_wrong_credentials(authorization: str | None) -> None:
    with pytest.raises(ReviewAuthenticationRejected):
        authenticate_review_operator(
            authorization=authorization,
            settings=configured_settings(),
        )


def test_rejects_review_operations_when_authentication_is_unconfigured() -> None:
    with pytest.raises(ReviewAuthenticationUnavailable):
        authenticate_review_operator(authorization=f"Bearer {TOKEN}", settings=Settings())


def test_rejects_a_short_review_operator_token() -> None:
    with pytest.raises(ValidationError):
        Settings(review_operator_token=SecretStr("too-short"))


def test_rejects_a_blank_review_operator_id() -> None:
    with pytest.raises(ValidationError):
        Settings(review_operator_id="   ")
