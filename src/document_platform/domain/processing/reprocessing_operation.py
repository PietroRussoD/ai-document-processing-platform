"""Immutable operator-requested processing recovery."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

MAX_IDEMPOTENCY_KEY_LENGTH = 128
MAX_OPERATOR_ID_LENGTH = 128
MAX_REASON_LENGTH = 500
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class InvalidReprocessingOperation(ValueError):
    """Raised when a reprocessing operation violates a domain invariant."""


class ConflictingReprocessingIdempotencyKey(ValueError):
    """Raised when an idempotency key is replayed with a different request."""


@dataclass(frozen=True, slots=True)
class ReprocessingOperation:
    id: UUID
    document_id: UUID
    source_run_id: UUID
    replacement_run_id: UUID
    requested_by: str
    reason: str
    idempotency_key: str
    request_fingerprint: str
    requested_at: datetime

    def __post_init__(self) -> None:
        for field_name, value in (
            ("id", self.id),
            ("document_id", self.document_id),
            ("source_run_id", self.source_run_id),
            ("replacement_run_id", self.replacement_run_id),
        ):
            if value.int == 0:
                raise InvalidReprocessingOperation(f"{field_name} must not be the nil UUID")
        if self.source_run_id == self.replacement_run_id:
            raise InvalidReprocessingOperation("source_run_id must differ from replacement_run_id")
        _validate_trimmed("requested_by", self.requested_by, MAX_OPERATOR_ID_LENGTH)
        _validate_trimmed("reason", self.reason, MAX_REASON_LENGTH)
        _validate_idempotency_key(self.idempotency_key)
        if SHA256_PATTERN.fullmatch(self.request_fingerprint) is None:
            raise InvalidReprocessingOperation(
                "request_fingerprint must be a lowercase SHA-256 digest"
            )
        if not _is_timezone_aware(self.requested_at):
            raise InvalidReprocessingOperation("requested_at must be timezone-aware")

    @classmethod
    def request(
        cls,
        *,
        operation_id: UUID,
        document_id: UUID,
        source_run_id: UUID,
        replacement_run_id: UUID,
        requested_by: str,
        reason: str,
        idempotency_key: str,
        requested_at: datetime,
    ) -> "ReprocessingOperation":
        return cls(
            id=operation_id,
            document_id=document_id,
            source_run_id=source_run_id,
            replacement_run_id=replacement_run_id,
            requested_by=requested_by,
            reason=reason,
            idempotency_key=idempotency_key,
            request_fingerprint=_request_fingerprint(
                document_id=document_id,
                source_run_id=source_run_id,
                reason=reason,
            ),
            requested_at=requested_at,
        )

    def ensure_replay_matches(self, *, source_run_id: UUID, reason: str) -> None:
        fingerprint = _request_fingerprint(
            document_id=self.document_id,
            source_run_id=source_run_id,
            reason=reason,
        )
        if fingerprint != self.request_fingerprint:
            raise ConflictingReprocessingIdempotencyKey(self.idempotency_key)


def _request_fingerprint(*, document_id: UUID, source_run_id: UUID, reason: str) -> str:
    canonical_request = json.dumps(
        {
            "document_id": str(document_id),
            "reason": reason,
            "source_run_id": str(source_run_id),
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(canonical_request).hexdigest()


def _validate_trimmed(field_name: str, value: str, maximum_length: int) -> None:
    if not value or value != value.strip():
        raise InvalidReprocessingOperation(f"{field_name} must be non-empty and trimmed")
    if len(value) > maximum_length:
        raise InvalidReprocessingOperation(
            f"{field_name} must be at most {maximum_length} characters"
        )


def _validate_idempotency_key(value: str) -> None:
    if not value or value != value.strip():
        raise InvalidReprocessingOperation("idempotency_key must be non-empty and trimmed")
    if len(value) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise InvalidReprocessingOperation(
            f"idempotency_key must be at most {MAX_IDEMPOTENCY_KEY_LENGTH} characters"
        )
    if not value.isascii() or not value.isprintable():
        raise InvalidReprocessingOperation(
            "idempotency_key must contain printable ASCII characters"
        )


def _is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None
