"""PostgreSQL read-model implementations."""

from document_platform.adapters.outbound.postgresql.queries.document_status_reader import (
    SqlAlchemyDocumentStatusReader,
)

__all__ = ["SqlAlchemyDocumentStatusReader"]
