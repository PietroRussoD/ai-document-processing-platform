"""Contracts implemented by outbound adapters."""

from document_platform.application.ports.blob_store import (
    BlobIntegrityConflict,
    BlobNotFound,
    BlobStore,
    BlobTooLarge,
    EmptyBlob,
    StoredBlob,
)
from document_platform.application.ports.document_repository import (
    ConcurrentDocumentUpdate,
    DocumentAlreadyExists,
    DocumentRepository,
)
from document_platform.application.ports.document_status_reader import (
    DocumentStatusReader,
    DocumentStatusView,
    ProcessingRunStatusView,
)
from document_platform.application.ports.pdf_inspector import (
    EncryptedPdf,
    InvalidPdf,
    PdfInspection,
    PdfInspector,
    PdfPageLimitExceeded,
)
from document_platform.application.ports.pdf_text_extractor import (
    ExtractedPdfText,
    PdfTextExtractor,
    PdfTextLimitExceeded,
)
from document_platform.application.ports.processing_run_repository import (
    ConcurrentProcessingRunUpdate,
    ProcessingRunAlreadyExists,
    ProcessingRunRepository,
)
from document_platform.application.ports.runtime import Clock, IdGenerator
from document_platform.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from document_platform.application.ports.upload_idempotency_repository import (
    UploadIdempotencyRecordAlreadyExists,
    UploadIdempotencyRepository,
)
from document_platform.application.ports.workflow_start_request_repository import (
    ConcurrentWorkflowStartRequestUpdate,
    WorkflowStartRequestAlreadyExists,
    WorkflowStartRequestRepository,
)
from document_platform.application.ports.workflow_starter import WorkflowStarter

__all__ = [
    "BlobIntegrityConflict",
    "BlobNotFound",
    "BlobStore",
    "BlobTooLarge",
    "Clock",
    "ConcurrentDocumentUpdate",
    "ConcurrentProcessingRunUpdate",
    "ConcurrentWorkflowStartRequestUpdate",
    "DocumentAlreadyExists",
    "DocumentRepository",
    "DocumentStatusReader",
    "DocumentStatusView",
    "EmptyBlob",
    "EncryptedPdf",
    "IdGenerator",
    "InvalidPdf",
    "ExtractedPdfText",
    "PdfInspection",
    "PdfInspector",
    "PdfPageLimitExceeded",
    "PdfTextExtractor",
    "PdfTextLimitExceeded",
    "ProcessingRunAlreadyExists",
    "ProcessingRunRepository",
    "ProcessingRunStatusView",
    "StoredBlob",
    "UnitOfWork",
    "UnitOfWorkFactory",
    "UploadIdempotencyRecordAlreadyExists",
    "UploadIdempotencyRepository",
    "WorkflowStartRequestAlreadyExists",
    "WorkflowStartRequestRepository",
    "WorkflowStarter",
]
