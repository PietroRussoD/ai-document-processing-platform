"""SQLAlchemy processing-run repository."""

from typing import Any, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from document_platform.adapters.outbound.postgresql.errors import (
    is_unique_violation,
    unique_constraint_name,
)
from document_platform.adapters.outbound.postgresql.models import ProcessingRunRecord
from document_platform.application.ports import (
    ActiveProcessingRunAlreadyExists,
    ConcurrentProcessingRunUpdate,
    ProcessingRunAlreadyExists,
)
from document_platform.domain.processing import ProcessingRun, ProcessingRunStatus

ACTIVE_PROCESSING_RUN_CONSTRAINT = "uq_processing_runs_document_id_active"


class SqlAlchemyProcessingRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, run: ProcessingRun) -> None:
        self._session.add(_to_record(run))
        try:
            await self._session.flush()
        except IntegrityError as error:
            if is_unique_violation(error) and unique_constraint_name(error) == "pk_processing_runs":
                raise ProcessingRunAlreadyExists(run.id) from error
            if (
                is_unique_violation(error)
                and unique_constraint_name(error) == ACTIVE_PROCESSING_RUN_CONSTRAINT
            ):
                raise ActiveProcessingRunAlreadyExists(run.document_id) from error
            raise

    async def get(self, run_id: UUID) -> ProcessingRun | None:
        record = await self._session.get(ProcessingRunRecord, run_id)
        return _to_domain(record) if record is not None else None

    async def get_latest_for_document(self, document_id: UUID) -> ProcessingRun | None:
        record = await self._session.scalar(
            select(ProcessingRunRecord)
            .where(ProcessingRunRecord.document_id == document_id)
            .order_by(ProcessingRunRecord.queued_at.desc(), ProcessingRunRecord.id.desc())
            .limit(1)
            .with_for_update()
        )
        return _to_domain(record) if record is not None else None

    async def update(self, run: ProcessingRun) -> None:
        if run.version < 1:
            raise ValueError("an updated processing run must have a positive version")

        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(ProcessingRunRecord)
                .where(
                    ProcessingRunRecord.id == run.id,
                    ProcessingRunRecord.version == run.version - 1,
                )
                .values(
                    status=run.status.value,
                    started_at=run.started_at,
                    status_changed_at=run.status_changed_at,
                    finished_at=run.finished_at,
                    attempt_count=run.attempt_count,
                    version=run.version,
                )
            ),
        )
        if result.rowcount != 1:
            raise ConcurrentProcessingRunUpdate(run.id)


def _to_record(run: ProcessingRun) -> ProcessingRunRecord:
    return ProcessingRunRecord(
        id=run.id,
        document_id=run.document_id,
        previous_run_id=run.previous_run_id,
        status=run.status.value,
        queued_at=run.queued_at,
        started_at=run.started_at,
        status_changed_at=run.status_changed_at,
        finished_at=run.finished_at,
        attempt_count=run.attempt_count,
        version=run.version,
    )


def _to_domain(record: ProcessingRunRecord) -> ProcessingRun:
    return ProcessingRun(
        id=record.id,
        document_id=record.document_id,
        previous_run_id=record.previous_run_id,
        status=ProcessingRunStatus(record.status),
        queued_at=record.queued_at,
        started_at=record.started_at,
        status_changed_at=record.status_changed_at,
        finished_at=record.finished_at,
        attempt_count=record.attempt_count,
        version=record.version,
    )
