"""Upload idempotency rule tests."""

import pytest

from document_platform.application.upload_idempotency import (
    ConflictingIdempotencyKey,
    IdempotencyKey,
    InvalidIdempotencyKey,
    UploadIdempotencyRecord,
    UploadRequestFingerprint,
)


def fingerprint(
    *,
    filename: str = "supplier-invoice.pdf",
    content_sha256: str = "a" * 64,
) -> UploadRequestFingerprint:
    return UploadRequestFingerprint.create(
        original_filename=filename,
        media_type="application/pdf",
        content_sha256=content_sha256,
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        " ",
        " padded",
        "padded ",
        "line\nbreak",
        "non-ascii-\N{LATIN SMALL LETTER E WITH GRAVE}",
        "a" * 129,
    ],
)
def test_rejects_invalid_idempotency_keys(value: str) -> None:
    with pytest.raises(InvalidIdempotencyKey):
        IdempotencyKey(value)


def test_accepts_an_opaque_printable_ascii_key() -> None:
    key = IdempotencyKey("upload:client-42/request_2026.09.14")

    assert key.value == "upload:client-42/request_2026.09.14"


def test_builds_a_deterministic_upload_request_fingerprint() -> None:
    assert fingerprint() == fingerprint()
    assert fingerprint(filename="purchase-order.pdf") != fingerprint()
    assert fingerprint(content_sha256="b" * 64) != fingerprint()


def test_allows_replay_for_the_same_request() -> None:
    request_fingerprint = fingerprint()
    record = UploadIdempotencyRecord(
        key=IdempotencyKey("request-42"),
        request_fingerprint=request_fingerprint,
    )

    record.ensure_replay_matches(request_fingerprint)


def test_rejects_key_reuse_for_a_different_request() -> None:
    record = UploadIdempotencyRecord(
        key=IdempotencyKey("request-42"),
        request_fingerprint=fingerprint(),
    )

    with pytest.raises(ConflictingIdempotencyKey, match="request-42"):
        record.ensure_replay_matches(fingerprint(content_sha256="b" * 64))


def test_rejects_an_invalid_request_fingerprint() -> None:
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        UploadRequestFingerprint("invalid")
