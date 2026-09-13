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
from document_platform.application.ports.runtime import Clock, IdGenerator
from document_platform.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

__all__ = [
    "Clock",
    "ConcurrentDocumentUpdate",
    "ConcurrentProcessingRunUpdate",
    "DocumentAlreadyExists",
    "DocumentRepository",
    "IdGenerator",
    "ProcessingRunAlreadyExists",
    "ProcessingRunRepository",
    "UnitOfWork",
    "UnitOfWorkFactory",
]
