"""Document aggregate and lifecycle rules."""

import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from pathlib import PurePath
from typing import Self
from uuid import UUID

PDF_MEDIA_TYPE = "application/pdf"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class DocumentStatus(StrEnum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class InvalidDocument(ValueError):
    """Raised when document metadata violates a domain invariant."""


class InvalidDocumentTransition(ValueError):
    """Raised when a document lifecycle transition is not allowed."""


_ALLOWED_TRANSITIONS: dict[DocumentStatus, frozenset[DocumentStatus]] = {
    DocumentStatus.UPLOADED: frozenset({DocumentStatus.PROCESSING}),
    DocumentStatus.PROCESSING: frozenset({DocumentStatus.REVIEW_REQUIRED, DocumentStatus.APPROVED}),
    DocumentStatus.REVIEW_REQUIRED: frozenset({DocumentStatus.APPROVED, DocumentStatus.REJECTED}),
    DocumentStatus.APPROVED: frozenset({DocumentStatus.PROCESSING}),
    DocumentStatus.REJECTED: frozenset({DocumentStatus.PROCESSING}),
}


@dataclass(frozen=True, slots=True)
class Document:
    id: UUID
    original_filename: str
    media_type: str
    size_bytes: int
    page_count: int
    content_sha256: str
    storage_key: str
    status: DocumentStatus
    accepted_at: datetime
    status_changed_at: datetime
    version: int

    def __post_init__(self) -> None:
        if self.id.int == 0:
            raise InvalidDocument("id must not be the nil UUID")
        validate_original_filename(self.original_filename)
        if self.media_type != PDF_MEDIA_TYPE:
            raise InvalidDocument(f"unsupported media_type: {self.media_type}")
        if self.size_bytes <= 0:
            raise InvalidDocument("size_bytes must be positive")
        if self.page_count <= 0:
            raise InvalidDocument("page_count must be positive")
        if SHA256_PATTERN.fullmatch(self.content_sha256) is None:
            raise InvalidDocument("content_sha256 must be a lowercase SHA-256 digest")
        if not self.storage_key.strip():
            raise InvalidDocument("storage_key must not be blank")
        if not _is_timezone_aware(self.accepted_at):
            raise InvalidDocument("accepted_at must be timezone-aware")
        if not _is_timezone_aware(self.status_changed_at):
            raise InvalidDocument("status_changed_at must be timezone-aware")
        if self.status_changed_at < self.accepted_at:
            raise InvalidDocument("status_changed_at must not precede accepted_at")
        if self.version < 0:
            raise InvalidDocument("version must not be negative")

    @classmethod
    def accept_pdf(
        cls,
        *,
        document_id: UUID,
        original_filename: str,
        size_bytes: int,
        page_count: int,
        content_sha256: str,
        storage_key: str,
        accepted_at: datetime,
    ) -> Self:
        return cls(
            id=document_id,
            original_filename=original_filename,
            media_type=PDF_MEDIA_TYPE,
            size_bytes=size_bytes,
            page_count=page_count,
            content_sha256=content_sha256,
            storage_key=storage_key,
            status=DocumentStatus.UPLOADED,
            accepted_at=accepted_at,
            status_changed_at=accepted_at,
            version=0,
        )

    def start_processing(self, *, at: datetime) -> Self:
        return self._transition_to(DocumentStatus.PROCESSING, at=at)

    def require_review(self, *, at: datetime) -> Self:
        return self._transition_to(DocumentStatus.REVIEW_REQUIRED, at=at)

    def approve(self, *, at: datetime) -> Self:
        return self._transition_to(DocumentStatus.APPROVED, at=at)

    def reject(self, *, at: datetime) -> Self:
        return self._transition_to(DocumentStatus.REJECTED, at=at)

    def reopen_for_reprocessing(self, *, at: datetime) -> Self:
        self._require_terminal_status(operation="reopen for reprocessing")
        return self._transition_to(DocumentStatus.PROCESSING, at=at)

    def _require_terminal_status(self, *, operation: str) -> None:
        if self.status not in {DocumentStatus.APPROVED, DocumentStatus.REJECTED}:
            raise InvalidDocumentTransition(f"cannot {operation} from {self.status}")

    def _transition_to(self, target: DocumentStatus, *, at: datetime) -> Self:
        if target not in _ALLOWED_TRANSITIONS[self.status]:
            raise InvalidDocumentTransition(f"cannot transition from {self.status} to {target}")
        if not _is_timezone_aware(at):
            raise InvalidDocumentTransition("transition time must be timezone-aware")
        if at < self.status_changed_at:
            raise InvalidDocumentTransition("transition time must not move backwards")

        return replace(
            self,
            status=target,
            status_changed_at=at,
            version=self.version + 1,
        )


def _is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def validate_original_filename(value: str) -> None:
    if not value.strip():
        raise InvalidDocument("original_filename must not be blank")
    if PurePath(value).name != value or "\\" in value:
        raise InvalidDocument("original_filename must not contain a path")
