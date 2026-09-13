"""Contracts implemented by outbound adapters."""

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
from document_platform.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

__all__ = [
    "ConcurrentDocumentUpdate",
    "DocumentAlreadyExists",
    "DocumentRepository",
    "ConcurrentProcessingRunUpdate",
    "ProcessingRunAlreadyExists",
    "ProcessingRunRepository",
    "UnitOfWork",
    "UnitOfWorkFactory",
]
