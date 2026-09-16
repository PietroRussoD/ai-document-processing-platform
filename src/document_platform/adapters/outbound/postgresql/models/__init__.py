"""PostgreSQL persistence models."""

from document_platform.adapters.outbound.postgresql.metadata import Base
from document_platform.adapters.outbound.postgresql.models.document_ocr_extraction_record import (
    DocumentOcrExtractionRecord,
)
from document_platform.adapters.outbound.postgresql.models.document_record import (
    DocumentRecord,
)
from document_platform.adapters.outbound.postgresql.models.document_text_extraction_record import (
    DocumentTextExtractionRecord,
)
from document_platform.adapters.outbound.postgresql.models.processing_run_record import (
    ProcessingRunRecord,
)
from document_platform.adapters.outbound.postgresql.models.upload_idempotency_record import (
    UploadIdempotencyRecordRow,
)
from document_platform.adapters.outbound.postgresql.models.workflow_start_request_record import (
    WorkflowStartRequestRecord,
)

__all__ = [
    "Base",
    "DocumentRecord",
    "DocumentTextExtractionRecord",
    "DocumentOcrExtractionRecord",
    "ProcessingRunRecord",
    "UploadIdempotencyRecordRow",
    "WorkflowStartRequestRecord",
]
