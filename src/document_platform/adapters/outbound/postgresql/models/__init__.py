"""PostgreSQL persistence models."""

from document_platform.adapters.outbound.postgresql.metadata import Base
from document_platform.adapters.outbound.postgresql.models.document_classification_record import (
    DocumentClassificationRecord,
)
from document_platform.adapters.outbound.postgresql.models.document_ocr_extraction_record import (
    DocumentOcrExtractionRecord,
)
from document_platform.adapters.outbound.postgresql.models.document_record import (
    DocumentRecord,
)
from document_platform.adapters.outbound.postgresql.models.document_text_extraction_record import (
    DocumentTextExtractionRecord,
)
from document_platform.adapters.outbound.postgresql.models.document_text_selection_record import (
    DocumentTextSelectionRecord,
)
from document_platform.adapters.outbound.postgresql.models.invoice_extraction_record import (
    InvoiceExtractionRecord,
)
from document_platform.adapters.outbound.postgresql.models.invoice_review_correction_record import (
    InvoiceReviewCorrectionRecord,
)
from document_platform.adapters.outbound.postgresql.models.invoice_validation_record import (
    InvoiceValidationRecord,
)
from document_platform.adapters.outbound.postgresql.models.processing_run_record import (
    ProcessingRunRecord,
)
from document_platform.adapters.outbound.postgresql.models.reprocessing_operation_record import (
    ReprocessingOperationRecord,
)
from document_platform.adapters.outbound.postgresql.models.review_resolution_record import (
    ReviewResolutionRecord,
)
from document_platform.adapters.outbound.postgresql.models.upload_idempotency_record import (
    UploadIdempotencyRecordRow,
)
from document_platform.adapters.outbound.postgresql.models.workflow_start_request_record import (
    WorkflowStartRequestRecord,
)

from .ai_invoice_extraction_proposal_record import AiInvoiceExtractionProposalRecord
from .ai_invoice_proposal_failure_record import AiInvoiceProposalFailureRecord

__all__ = [
    "Base",
    "DocumentRecord",
    "DocumentTextExtractionRecord",
    "DocumentTextSelectionRecord",
    "DocumentOcrExtractionRecord",
    "DocumentClassificationRecord",
    "InvoiceExtractionRecord",
    "AiInvoiceExtractionProposalRecord",
    "AiInvoiceProposalFailureRecord",
    "InvoiceReviewCorrectionRecord",
    "InvoiceValidationRecord",
    "ProcessingRunRecord",
    "ReprocessingOperationRecord",
    "ReviewResolutionRecord",
    "UploadIdempotencyRecordRow",
    "WorkflowStartRequestRecord",
]
