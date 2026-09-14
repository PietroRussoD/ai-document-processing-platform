"""Upload idempotency rule tests."""

from datetime import UTC, datetime
from uuid import UUID

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


def record(request_fingerprint: UploadRequestFingerprint) -> UploadIdempotencyRecord:
    return UploadIdempotencyRecord(
        key=IdempotencyKey("request-42"),
        request_fingerprint=request_fingerprint,
        processing_run_id=UUID("7bb72e97-470a-4e79-9654-d6aa6fcd884d"),
        recorded_at=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
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
    accepted_upload = record(request_fingerprint)

    accepted_upload.ensure_replay_matches(request_fingerprint)


def test_rejects_key_reuse_for_a_different_request() -> None:
    accepted_upload = record(fingerprint())

    with pytest.raises(ConflictingIdempotencyKey, match="request-42"):
        accepted_upload.ensure_replay_matches(fingerprint(content_sha256="b" * 64))


def test_rejects_an_invalid_request_fingerprint() -> None:
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        UploadRequestFingerprint("invalid")


def test_rejects_a_nil_processing_run_id() -> None:
    with pytest.raises(ValueError, match="processing_run_id"):
        UploadIdempotencyRecord(
            key=IdempotencyKey("request-42"),
            request_fingerprint=fingerprint(),
            processing_run_id=UUID(int=0),
            recorded_at=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
        )


def test_rejects_a_naive_recorded_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        UploadIdempotencyRecord(
            key=IdempotencyKey("request-42"),
            request_fingerprint=fingerprint(),
            processing_run_id=UUID("7bb72e97-470a-4e79-9654-d6aa6fcd884d"),
            recorded_at=datetime(2026, 9, 14, 12, 0),
        )
