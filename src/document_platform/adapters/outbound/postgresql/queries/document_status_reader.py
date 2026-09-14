"""SQLAlchemy document-status read model."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from document_platform.adapters.outbound.postgresql.models import (
    DocumentRecord,
    ProcessingRunRecord,
)
from document_platform.application.ports import (
    DocumentStatusView,
    ProcessingRunStatusView,
)
from document_platform.domain.documents import DocumentStatus
from document_platform.domain.processing import ProcessingRunStatus


class SqlAlchemyDocumentStatusReader:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get(self, document_id: UUID) -> DocumentStatusView | None:
        statement = (
            select(DocumentRecord, ProcessingRunRecord)
            .join(ProcessingRunRecord, ProcessingRunRecord.document_id == DocumentRecord.id)
            .where(DocumentRecord.id == document_id)
            .order_by(ProcessingRunRecord.queued_at.desc(), ProcessingRunRecord.id.desc())
            .limit(1)
        )
        async with self._sessions() as session:
            row = (await session.execute(statement)).one_or_none()

        if row is None:
            return None

        document = row[0]
        run = row[1]
        return DocumentStatusView(
            id=document.id,
            original_filename=document.original_filename,
            media_type=document.media_type,
            size_bytes=document.size_bytes,
            page_count=document.page_count,
            content_sha256=document.content_sha256,
            status=DocumentStatus(document.status),
            accepted_at=document.accepted_at,
            status_changed_at=document.status_changed_at,
            current_run=ProcessingRunStatusView(
                id=run.id,
                status=ProcessingRunStatus(run.status),
                queued_at=run.queued_at,
                started_at=run.started_at,
                status_changed_at=run.status_changed_at,
                finished_at=run.finished_at,
                attempt_count=run.attempt_count,
            ),
        )
