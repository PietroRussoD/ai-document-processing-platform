"""Transactional database deletion of terminal retention candidates."""

from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from document_platform.adapters.outbound.postgresql.models import DocumentRecord
from document_platform.application.ports import DocumentRetentionSnapshot
from document_platform.domain.documents import RETENTION_ELIGIBLE_STATUSES, DocumentStatus


class SqlAlchemyDocumentRetentionDeleter:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def delete_candidates(self, *, cutoff: datetime) -> DocumentRetentionSnapshot:
        statement = (
            delete(DocumentRecord)
            .where(
                DocumentRecord.status.in_(RETENTION_ELIGIBLE_STATUSES),
                DocumentRecord.status_changed_at < cutoff,
            )
            .returning(DocumentRecord.status, DocumentRecord.size_bytes)
        )
        async with self._sessions.begin() as session:
            rows = (await session.execute(statement)).all()

        counts_by_status: dict[DocumentStatus, int] = {}
        total_size_bytes = 0
        for status, size_bytes in rows:
            document_status = DocumentStatus(status)
            counts_by_status[document_status] = counts_by_status.get(document_status, 0) + 1
            total_size_bytes += size_bytes

        return DocumentRetentionSnapshot(
            counts_by_status=counts_by_status,
            total_size_bytes=total_size_bytes,
        )
