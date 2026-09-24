"""Delete database records eligible for document retention."""

from datetime import datetime
from typing import Protocol

from document_platform.application.ports.document_retention_reader import (
    DocumentRetentionSnapshot,
)


class DocumentRetentionDeleter(Protocol):
    async def delete_candidates(self, *, cutoff: datetime) -> DocumentRetentionSnapshot: ...
