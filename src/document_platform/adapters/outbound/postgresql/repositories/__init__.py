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

from . import (
    document_classification_repository,
    document_ocr_extraction_repository,
    document_text_extraction_repository,
    document_text_selection_repository,
    invoice_extraction_repository,
    invoice_validation_repository,
)
from .workflow_start_request_repository import SqlAlchemyWorkflowStartRequestRepository

SqlAlchemyDocumentTextExtractionRepository = (
    document_text_extraction_repository.SqlAlchemyDocumentTextExtractionRepository
)
SqlAlchemyDocumentOcrExtractionRepository = (
    document_ocr_extraction_repository.SqlAlchemyDocumentOcrExtractionRepository
)
SqlAlchemyDocumentClassificationRepository = (
    document_classification_repository.SqlAlchemyDocumentClassificationRepository
)
SqlAlchemyDocumentTextSelectionRepository = (
    document_text_selection_repository.SqlAlchemyDocumentTextSelectionRepository
)
SqlAlchemyInvoiceExtractionRepository = (
    invoice_extraction_repository.SqlAlchemyInvoiceExtractionRepository
)
SqlAlchemyInvoiceValidationRepository = (
    invoice_validation_repository.SqlAlchemyInvoiceValidationRepository
)

__all__ = [
    "SqlAlchemyDocumentRepository",
    "SqlAlchemyDocumentOcrExtractionRepository",
    "SqlAlchemyDocumentClassificationRepository",
    "SqlAlchemyDocumentTextExtractionRepository",
    "SqlAlchemyDocumentTextSelectionRepository",
    "SqlAlchemyInvoiceExtractionRepository",
    "SqlAlchemyInvoiceValidationRepository",
    "SqlAlchemyProcessingRunRepository",
    "SqlAlchemyUploadIdempotencyRepository",
    "SqlAlchemyWorkflowStartRequestRepository",
]
