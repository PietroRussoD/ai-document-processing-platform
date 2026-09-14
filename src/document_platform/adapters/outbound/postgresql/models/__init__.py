"""PostgreSQL persistence models."""

from document_platform.adapters.outbound.postgresql.metadata import Base
from document_platform.adapters.outbound.postgresql.models.document_record import (
    DocumentRecord,
)
from document_platform.adapters.outbound.postgresql.models.processing_run_record import (
    ProcessingRunRecord,
)
from document_platform.adapters.outbound.postgresql.models.upload_idempotency_record import (
    UploadIdempotencyRecordRow,
)

__all__ = [
    "Base",
    "DocumentRecord",
    "ProcessingRunRecord",
    "UploadIdempotencyRecordRow",
]
