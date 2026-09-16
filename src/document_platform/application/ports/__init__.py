"""Contracts implemented by outbound adapters."""

from document_platform.application.ports.blob_store import (
    BlobIntegrityConflict,
    BlobNotFound,
    BlobStore,
    BlobTooLarge,
    EmptyBlob,
    StoredBlob,
)
from document_platform.application.ports.document_classification_repository import (
    DocumentClassificationAlreadyExists,
    DocumentClassificationRepository,
)
from document_platform.application.ports.document_ocr_extraction_repository import (
    DocumentOcrExtractionAlreadyExists,
    DocumentOcrExtractionRepository,
)
from document_platform.application.ports.document_repository import (
    ConcurrentDocumentUpdate,
    DocumentAlreadyExists,
    DocumentRepository,
)
from document_platform.application.ports.document_status_reader import (
    ClassificationMetadataView,
    DocumentStatusReader,
    DocumentStatusView,
    OcrExtractionMetadataView,
    ProcessingOutputView,
    ProcessingRunStatusView,
    TextExtractionMetadataView,
    TextSelectionMetadataView,
)
from document_platform.application.ports.document_text_extraction_repository import (
    DocumentTextExtractionAlreadyExists,
    DocumentTextExtractionRepository,
)
from document_platform.application.ports.document_text_selection_repository import (
    DocumentTextSelectionAlreadyExists,
    DocumentTextSelectionRepository,
)
from document_platform.application.ports.pdf_inspector import (
    EncryptedPdf,
    InvalidPdf,
    PdfInspection,
    PdfInspector,
    PdfPageLimitExceeded,
)
from document_platform.application.ports.pdf_ocr_extractor import (
    ExtractedOcrText,
    OcrEngineUnavailable,
    OcrExtractionFailed,
    OcrTextLimitExceeded,
    PdfOcrExtractor,
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
    "ClassificationMetadataView",
    "ConcurrentDocumentUpdate",
    "ConcurrentProcessingRunUpdate",
    "ConcurrentWorkflowStartRequestUpdate",
    "DocumentAlreadyExists",
    "DocumentTextExtractionAlreadyExists",
    "DocumentTextExtractionRepository",
    "DocumentTextSelectionAlreadyExists",
    "DocumentTextSelectionRepository",
    "DocumentRepository",
    "DocumentOcrExtractionAlreadyExists",
    "DocumentOcrExtractionRepository",
    "DocumentClassificationAlreadyExists",
    "DocumentClassificationRepository",
    "DocumentStatusReader",
    "DocumentStatusView",
    "EmptyBlob",
    "EncryptedPdf",
    "IdGenerator",
    "InvalidPdf",
    "ExtractedPdfText",
    "ExtractedOcrText",
    "PdfInspection",
    "PdfOcrExtractor",
    "PdfInspector",
    "PdfPageLimitExceeded",
    "PdfTextExtractor",
    "PdfTextLimitExceeded",
    "OcrEngineUnavailable",
    "OcrExtractionFailed",
    "OcrTextLimitExceeded",
    "OcrExtractionMetadataView",
    "ProcessingOutputView",
    "ProcessingRunAlreadyExists",
    "ProcessingRunRepository",
    "ProcessingRunStatusView",
    "StoredBlob",
    "TextExtractionMetadataView",
    "TextSelectionMetadataView",
    "UnitOfWork",
    "UnitOfWorkFactory",
    "UploadIdempotencyRecordAlreadyExists",
    "UploadIdempotencyRepository",
    "WorkflowStartRequestAlreadyExists",
    "WorkflowStartRequestRepository",
    "WorkflowStarter",
]
