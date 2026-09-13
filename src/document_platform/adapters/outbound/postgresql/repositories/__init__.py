"""SQLAlchemy repository implementations."""

from document_platform.adapters.outbound.postgresql.repositories.document_repository import (
    SqlAlchemyDocumentRepository,
)

__all__ = ["SqlAlchemyDocumentRepository"]
