"""PostgreSQL summary of terminal documents eligible for retention."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from document_platform.adapters.outbound.postgresql.models import DocumentRecord
from document_platform.application.ports import DocumentRetentionSnapshot
from document_platform.domain.documents import DocumentStatus

_ELIGIBLE_STATUSES = (
    DocumentStatus.APPROVED,
    DocumentStatus.REJECTED,
    DocumentStatus.FAILED,
)


class SqlAlchemyDocumentRetentionReader:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def summarize_candidates(self, *, cutoff: datetime) -> DocumentRetentionSnapshot:
        statement = (
            select(
                DocumentRecord.status,
                func.count(DocumentRecord.id),
                func.coalesce(func.sum(DocumentRecord.size_bytes), 0),
            )
            .where(
                DocumentRecord.status.in_(_ELIGIBLE_STATUSES),
                DocumentRecord.status_changed_at < cutoff,
            )
            .group_by(DocumentRecord.status)
        )
        async with self._sessions() as session:
            rows = (await session.execute(statement)).all()

        return DocumentRetentionSnapshot(
            counts_by_status={DocumentStatus(status): count for status, count, _ in rows},
            total_size_bytes=sum(size_bytes for _, _, size_bytes in rows),
        )
