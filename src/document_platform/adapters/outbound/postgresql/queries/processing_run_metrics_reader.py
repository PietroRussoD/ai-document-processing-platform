"""PostgreSQL operational snapshot for processing-run metrics."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from document_platform.adapters.outbound.postgresql.models import ProcessingRunRecord
from document_platform.application.ports import ProcessingRunMetricsSnapshot
from document_platform.domain.processing import ProcessingRunStatus


class SqlAlchemyProcessingRunMetricsReader:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def read(self) -> ProcessingRunMetricsSnapshot:
        counts_statement = select(
            ProcessingRunRecord.status,
            func.count(ProcessingRunRecord.id),
        ).group_by(ProcessingRunRecord.status)
        oldest_queued_statement = select(func.min(ProcessingRunRecord.queued_at)).where(
            ProcessingRunRecord.status == ProcessingRunStatus.QUEUED
        )
        async with self._sessions() as session:
            rows = (await session.execute(counts_statement)).all()
            oldest_queued_at = (await session.execute(oldest_queued_statement)).scalar_one()

        return ProcessingRunMetricsSnapshot(
            counts_by_status={ProcessingRunStatus(status): count for status, count in rows},
            oldest_queued_at=oldest_queued_at,
        )
