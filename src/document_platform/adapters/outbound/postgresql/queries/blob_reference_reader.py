"""PostgreSQL lookup for document references to a stored blob."""

from collections.abc import Collection

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from document_platform.adapters.outbound.postgresql.models import DocumentRecord
from document_platform.application.ports import BlobIdentity


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

    async def find_referenced(self, blobs: Collection[BlobIdentity]) -> frozenset[BlobIdentity]:
        if not blobs:
            return frozenset()
        statement = (
            select(DocumentRecord.storage_key, DocumentRecord.content_sha256)
            .where(
                tuple_(DocumentRecord.storage_key, DocumentRecord.content_sha256).in_(
                    [(blob.key, blob.content_sha256) for blob in blobs]
                )
            )
            .distinct()
        )
        async with self._sessions() as session:
            rows = (await session.execute(statement)).all()
        return frozenset(BlobIdentity(key, digest) for key, digest in rows)
