"""Document-status read model contract."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from document_platform.domain.documents import DocumentStatus
from document_platform.domain.processing import ProcessingRunStatus


@dataclass(frozen=True, slots=True)
class ProcessingRunStatusView:
    id: UUID
    status: ProcessingRunStatus
    queued_at: datetime
    started_at: datetime | None
    status_changed_at: datetime
    finished_at: datetime | None
    attempt_count: int


@dataclass(frozen=True, slots=True)
class DocumentStatusView:
    id: UUID
    original_filename: str
    media_type: str
    size_bytes: int
    page_count: int
    content_sha256: str
    status: DocumentStatus
    accepted_at: datetime
    status_changed_at: datetime
    current_run: ProcessingRunStatusView


class DocumentStatusReader(Protocol):
    async def get(self, document_id: UUID) -> DocumentStatusView | None: ...
