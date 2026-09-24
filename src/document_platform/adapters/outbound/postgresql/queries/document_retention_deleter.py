"""Transactional database deletion of terminal retention candidates."""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from document_platform.adapters.outbound.postgresql.models import DocumentRecord
from document_platform.application.ports import DocumentRetentionSnapshot
from document_platform.domain.documents import RETENTION_ELIGIBLE_STATUSES, DocumentStatus


class SqlAlchemyDocumentRetentionDeleter:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], *, batch_size: int = 500
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self._sessions = sessions
        self._batch_size = batch_size

    async def delete_candidates(self, *, cutoff: datetime) -> DocumentRetentionSnapshot:
        counts_by_status: dict[DocumentStatus, int] = {}
        total_size_bytes = 0
        while True:
            async with self._sessions.begin() as session:
                candidate_ids = (
                    await session.scalars(
                        select(DocumentRecord.id)
                        .where(
                            DocumentRecord.status.in_(RETENTION_ELIGIBLE_STATUSES),
                            DocumentRecord.status_changed_at < cutoff,
                        )
                        .order_by(DocumentRecord.status_changed_at, DocumentRecord.id)
                        .limit(self._batch_size)
                        .with_for_update()
                    )
                ).all()
                if not candidate_ids:
                    break

                rows = (
                    await session.execute(
                        delete(DocumentRecord)
                        .where(DocumentRecord.id.in_(candidate_ids))
                        .returning(DocumentRecord.status, DocumentRecord.size_bytes)
                    )
                ).all()

            for status, size_bytes in rows:
                document_status = DocumentStatus(status)
                counts_by_status[document_status] = counts_by_status.get(document_status, 0) + 1
                total_size_bytes += size_bytes

        return DocumentRetentionSnapshot(
            counts_by_status=counts_by_status,
            total_size_bytes=total_size_bytes,
        )
