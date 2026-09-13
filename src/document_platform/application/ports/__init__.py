"""Contracts implemented by outbound adapters."""

from document_platform.application.ports.document_repository import (
    ConcurrentDocumentUpdate,
    DocumentAlreadyExists,
    DocumentRepository,
)
from document_platform.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

__all__ = [
    "ConcurrentDocumentUpdate",
    "DocumentAlreadyExists",
    "DocumentRepository",
    "UnitOfWork",
    "UnitOfWorkFactory",
]
