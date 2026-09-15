"""SQLAlchemy repository implementations."""

from document_platform.adapters.outbound.postgresql.repositories.document_repository import (
    SqlAlchemyDocumentRepository,
)
from document_platform.adapters.outbound.postgresql.repositories.idempotency_repository import (
    SqlAlchemyUploadIdempotencyRepository,
)
from document_platform.adapters.outbound.postgresql.repositories.processing_run_repository import (
    SqlAlchemyProcessingRunRepository,
)

from . import document_text_extraction_repository
from .workflow_start_request_repository import SqlAlchemyWorkflowStartRequestRepository

SqlAlchemyDocumentTextExtractionRepository = (
    document_text_extraction_repository.SqlAlchemyDocumentTextExtractionRepository
)

__all__ = [
    "SqlAlchemyDocumentRepository",
    "SqlAlchemyDocumentTextExtractionRepository",
    "SqlAlchemyProcessingRunRepository",
    "SqlAlchemyUploadIdempotencyRepository",
    "SqlAlchemyWorkflowStartRequestRepository",
]
