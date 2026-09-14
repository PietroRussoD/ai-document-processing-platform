"""Contracts implemented by outbound adapters."""

from document_platform.application.ports.blob_store import (
    BlobIntegrityConflict,
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

__all__ = [
    "BlobIntegrityConflict",
    "BlobStore",
    "BlobTooLarge",
    "Clock",
    "ConcurrentDocumentUpdate",
    "ConcurrentProcessingRunUpdate",
    "DocumentAlreadyExists",
    "DocumentRepository",
    "DocumentStatusReader",
    "DocumentStatusView",
    "EmptyBlob",
    "EncryptedPdf",
    "IdGenerator",
    "InvalidPdf",
    "PdfInspection",
    "PdfInspector",
    "PdfPageLimitExceeded",
    "ProcessingRunAlreadyExists",
    "ProcessingRunRepository",
    "ProcessingRunStatusView",
    "StoredBlob",
    "UnitOfWork",
    "UnitOfWorkFactory",
    "UploadIdempotencyRecordAlreadyExists",
    "UploadIdempotencyRepository",
]
