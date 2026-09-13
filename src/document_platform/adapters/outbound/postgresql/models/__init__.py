"""PostgreSQL persistence models."""

from document_platform.adapters.outbound.postgresql.metadata import Base
from document_platform.adapters.outbound.postgresql.models.document_record import (
    DocumentRecord,
)
from document_platform.adapters.outbound.postgresql.models.processing_run_record import (
    ProcessingRunRecord,
)

__all__ = ["Base", "DocumentRecord", "ProcessingRunRecord"]
