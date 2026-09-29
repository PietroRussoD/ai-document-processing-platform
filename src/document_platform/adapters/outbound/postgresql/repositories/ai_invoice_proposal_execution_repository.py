"""SQLAlchemy repository with one-way, concurrency-safe execution completion."""

from typing import Any, cast
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from document_platform.adapters.outbound.postgresql.errors import is_unique_violation
from document_platform.adapters.outbound.postgresql.models import AiInvoiceProposalExecutionRecord
from document_platform.application.ports.invoice_proposal_execution_repository import (
    AiInvoiceProposalExecutionAlreadyExists,
    ConcurrentAiInvoiceProposalExecutionUpdate,
)
from document_platform.domain.processing import (
    AiInvoiceProposalExecution,
    AiInvoiceProposalExecutionStatus,
)


class SqlAlchemyAiInvoiceProposalExecutionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, execution: AiInvoiceProposalExecution) -> None:
        if execution.status not in (
            AiInvoiceProposalExecutionStatus.DISABLED,
            AiInvoiceProposalExecutionStatus.RUNNING,
        ):
            raise ValueError("a new execution must be disabled or running")
        self._session.add(
            AiInvoiceProposalExecutionRecord(
                processing_run_id=execution.processing_run_id,
                status=execution.status.value,
                status_changed_at=execution.status_changed_at,
                started_at=execution.started_at,
                finished_at=execution.finished_at,
            )
        )
        try:
            await self._session.flush()
        except IntegrityError as error:
            if is_unique_violation(error):
                raise AiInvoiceProposalExecutionAlreadyExists(
                    execution.processing_run_id
                ) from error
            raise

    async def get(self, processing_run_id: UUID) -> AiInvoiceProposalExecution | None:
        record = await self._session.get(AiInvoiceProposalExecutionRecord, processing_run_id)
        if record is None:
            return None
        return AiInvoiceProposalExecution(
            processing_run_id=record.processing_run_id,
            status=AiInvoiceProposalExecutionStatus(record.status),
            status_changed_at=record.status_changed_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
        )

    async def finish(self, execution: AiInvoiceProposalExecution) -> None:
        if execution.status not in (
            AiInvoiceProposalExecutionStatus.COMPLETED,
            AiInvoiceProposalExecutionStatus.FAILED,
        ):
            raise ValueError("execution completion requires completed or failed status")
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(AiInvoiceProposalExecutionRecord)
                .where(
                    AiInvoiceProposalExecutionRecord.processing_run_id
                    == execution.processing_run_id,
                    AiInvoiceProposalExecutionRecord.status
                    == AiInvoiceProposalExecutionStatus.RUNNING.value,
                    AiInvoiceProposalExecutionRecord.started_at == execution.started_at,
                )
                .values(
                    status=execution.status.value,
                    status_changed_at=execution.status_changed_at,
                    finished_at=execution.finished_at,
                )
            ),
        )
        if result.rowcount != 1:
            raise ConcurrentAiInvoiceProposalExecutionUpdate(execution.processing_run_id)
