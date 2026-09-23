"""PostgreSQL operational snapshot for processing-run metrics."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from document_platform.adapters.outbound.postgresql.models import ProcessingRunRecord
from document_platform.application.ports import ProcessingRunMetricsSnapshot
from document_platform.domain.processing import (
    ProcessingFailureCode,
    ProcessingRunStatus,
    ProcessingStage,
)


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
        failure_counts_statement = (
            select(
                ProcessingRunRecord.failure_stage,
                ProcessingRunRecord.failure_code,
                func.count(ProcessingRunRecord.id),
            )
            .where(ProcessingRunRecord.status == ProcessingRunStatus.FAILED)
            .group_by(ProcessingRunRecord.failure_stage, ProcessingRunRecord.failure_code)
        )
        async with self._sessions() as session:
            rows = (await session.execute(counts_statement)).all()
            oldest_queued_at = (await session.execute(oldest_queued_statement)).scalar_one()
            failure_rows = (await session.execute(failure_counts_statement)).all()

        return ProcessingRunMetricsSnapshot(
            counts_by_status={ProcessingRunStatus(status): count for status, count in rows},
            oldest_queued_at=oldest_queued_at,
            failure_counts_by_category={
                (ProcessingStage(stage), ProcessingFailureCode(code)): count
                for stage, code, count in failure_rows
                if stage is not None and code is not None
            },
        )
