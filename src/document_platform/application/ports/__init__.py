"""Contracts implemented by outbound adapters."""

from document_platform.application.ports.blob_store import (
    BlobIntegrityConflict,
    BlobStore,
    BlobTooLarge,
    ByteStream,
    EmptyBlob,
    StoredBlob,
)
from document_platform.application.ports.document_repository import (
    ConcurrentDocumentUpdate,
    DocumentAlreadyExists,
    DocumentRepository,
)
from document_platform.application.ports.processing_run_repository import (
    ConcurrentProcessingRunUpdate,
    ProcessingRunAlreadyExists,
    ProcessingRunRepository,
)
from document_platform.application.ports.runtime import Clock, IdGenerator
from document_platform.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

__all__ = [
    "BlobIntegrityConflict",
    "BlobStore",
    "BlobTooLarge",
    "ByteStream",
    "Clock",
    "ConcurrentDocumentUpdate",
    "ConcurrentProcessingRunUpdate",
    "DocumentAlreadyExists",
    "DocumentRepository",
    "EmptyBlob",
    "IdGenerator",
    "ProcessingRunAlreadyExists",
    "ProcessingRunRepository",
    "StoredBlob",
    "UnitOfWork",
    "UnitOfWorkFactory",
]
