"""PostgreSQL lookup for document references to a stored blob."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from document_platform.adapters.outbound.postgresql.models import DocumentRecord


class SqlAlchemyBlobReferenceReader:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def is_referenced(self, *, key: str, content_sha256: str) -> bool:
        statement = (
            select(DocumentRecord.id)
            .where(
                DocumentRecord.content_sha256 == content_sha256,
                DocumentRecord.storage_key == key,
            )
            .limit(1)
        )
        async with self._sessions() as session:
            return (await session.scalar(statement)) is not None
