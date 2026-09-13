"""SQLAlchemy implementation of the application unit of work."""

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyProcessingRunRepository,
)
from document_platform.application.ports import DocumentRepository, ProcessingRunRepository


class SqlAlchemyUnitOfWork:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions
        self._session: AsyncSession | None = None
        self._documents: DocumentRepository | None = None
        self._processing_runs: ProcessingRunRepository | None = None

    @property
    def documents(self) -> DocumentRepository:
        if self._documents is None:
            raise RuntimeError("unit of work is not active")
        return self._documents

    @property
    def processing_runs(self) -> ProcessingRunRepository:
        if self._processing_runs is None:
            raise RuntimeError("unit of work is not active")
        return self._processing_runs

    async def __aenter__(self) -> Self:
        if self._session is not None:
            raise RuntimeError("unit of work is already active")

        self._session = self._sessions()
        self._documents = SqlAlchemyDocumentRepository(self._session)
        self._processing_runs = SqlAlchemyProcessingRunRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._require_session()
        try:
            await session.rollback()
        finally:
            await session.close()
            self._session = None
            self._documents = None
            self._processing_runs = None

    async def commit(self) -> None:
        await self._require_session().commit()

    async def rollback(self) -> None:
        await self._require_session().rollback()

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("unit of work is not active")
        return self._session
