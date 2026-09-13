"""Contracts implemented by outbound adapters."""

from document_platform.application.ports.document_repository import (
    ConcurrentDocumentUpdate,
    DocumentAlreadyExists,
    DocumentRepository,
)

__all__ = [
    "ConcurrentDocumentUpdate",
    "DocumentAlreadyExists",
    "DocumentRepository",
]
