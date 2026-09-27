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
    invoice_review_correction_repository,
    invoice_validation_repository,
    review_resolution_repository,
)
from .ai_invoice_extraction_proposal_repository import (
    SqlAlchemyAiInvoiceExtractionProposalRepository,
)
from .reprocessing_operation_repository import (
    SqlAlchemyReprocessingOperationRepository,
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
SqlAlchemyInvoiceReviewCorrectionRepository = (
    invoice_review_correction_repository.SqlAlchemyInvoiceReviewCorrectionRepository
)
SqlAlchemyInvoiceValidationRepository = (
    invoice_validation_repository.SqlAlchemyInvoiceValidationRepository
)
SqlAlchemyReviewResolutionRepository = (
    review_resolution_repository.SqlAlchemyReviewResolutionRepository
)

__all__ = [
    "SqlAlchemyDocumentRepository",
    "SqlAlchemyDocumentOcrExtractionRepository",
    "SqlAlchemyDocumentClassificationRepository",
    "SqlAlchemyDocumentTextExtractionRepository",
    "SqlAlchemyDocumentTextSelectionRepository",
    "SqlAlchemyInvoiceExtractionRepository",
    "SqlAlchemyAiInvoiceExtractionProposalRepository",
    "SqlAlchemyInvoiceReviewCorrectionRepository",
    "SqlAlchemyInvoiceValidationRepository",
    "SqlAlchemyReviewResolutionRepository",
    "SqlAlchemyProcessingRunRepository",
    "SqlAlchemyReprocessingOperationRepository",
    "SqlAlchemyUploadIdempotencyRepository",
    "SqlAlchemyWorkflowStartRequestRepository",
]
