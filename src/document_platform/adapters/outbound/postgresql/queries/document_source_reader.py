"""Resolve document identifiers to internal blob keys."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from document_platform.adapters.outbound.postgresql.models import DocumentRecord


class SqlAlchemyDocumentSourceReader:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get_storage_key(self, document_id: UUID) -> str | None:
        async with self._sessions() as session:
            return await session.scalar(
                select(DocumentRecord.storage_key).where(DocumentRecord.id == document_id)
            )
