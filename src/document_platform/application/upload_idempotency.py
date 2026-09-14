"""Upload idempotency values and replay rules."""

import hashlib
import json
import re
from dataclasses import dataclass

MAX_IDEMPOTENCY_KEY_LENGTH = 128
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class InvalidIdempotencyKey(ValueError):
    """Raised when a client idempotency key cannot be accepted."""


class ConflictingIdempotencyKey(ValueError):
    def __init__(self, key: str) -> None:
        super().__init__(f"idempotency key was already used for another upload: {key}")


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    value: str

    def __post_init__(self) -> None:
        if not self.value or self.value.strip() != self.value:
            raise InvalidIdempotencyKey("idempotency key must not be blank or padded")
        if len(self.value) > MAX_IDEMPOTENCY_KEY_LENGTH:
            raise InvalidIdempotencyKey(
                f"idempotency key must not exceed {MAX_IDEMPOTENCY_KEY_LENGTH} characters"
            )
        if not self.value.isascii() or not self.value.isprintable():
            raise InvalidIdempotencyKey("idempotency key must contain printable ASCII characters")


@dataclass(frozen=True, slots=True)
class UploadRequestFingerprint:
    value: str

    def __post_init__(self) -> None:
        if SHA256_PATTERN.fullmatch(self.value) is None:
            raise ValueError("upload request fingerprint must be a lowercase SHA-256 digest")

    @classmethod
    def create(
        cls,
        *,
        original_filename: str,
        media_type: str,
        content_sha256: str,
    ) -> "UploadRequestFingerprint":
        canonical_request = json.dumps(
            {
                "content_sha256": content_sha256,
                "media_type": media_type,
                "original_filename": original_filename,
            },
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        return cls(hashlib.sha256(canonical_request).hexdigest())


@dataclass(frozen=True, slots=True)
class UploadIdempotencyRecord:
    key: IdempotencyKey
    request_fingerprint: UploadRequestFingerprint

    def ensure_replay_matches(self, request_fingerprint: UploadRequestFingerprint) -> None:
        if request_fingerprint != self.request_fingerprint:
            raise ConflictingIdempotencyKey(self.key.value)
