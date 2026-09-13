"""PostgreSQL persistence adapters."""

from document_platform.adapters.outbound.postgresql.unit_of_work import (
    SqlAlchemyUnitOfWork,
)

__all__ = ["SqlAlchemyUnitOfWork"]
