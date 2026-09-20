"""SQLAlchemy repository for immutable reprocessing operations."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from document_platform.adapters.outbound.postgresql.errors import (
    is_unique_violation,
    unique_constraint_name,
)
from document_platform.adapters.outbound.postgresql.models import ReprocessingOperationRecord
from document_platform.application.ports import ReprocessingOperationAlreadyExists
from document_platform.domain.processing import ReprocessingOperation

IDEMPOTENCY_KEY_CONSTRAINT = "uq_reprocessing_operations_document_id_idempotency_key"


class SqlAlchemyReprocessingOperationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, operation: ReprocessingOperation) -> None:
        self._session.add(_to_record(operation))
        try:
            await self._session.flush()
        except IntegrityError as error:
            if (
                is_unique_violation(error)
                and unique_constraint_name(error) == IDEMPOTENCY_KEY_CONSTRAINT
            ):
                raise ReprocessingOperationAlreadyExists(
                    document_id=operation.document_id,
                    idempotency_key=operation.idempotency_key,
                ) from error
            raise

    async def get(
        self,
        *,
        document_id: UUID,
        idempotency_key: str,
    ) -> ReprocessingOperation | None:
        record = await self._session.scalar(
            select(ReprocessingOperationRecord).where(
                ReprocessingOperationRecord.document_id == document_id,
                ReprocessingOperationRecord.idempotency_key == idempotency_key,
            )
        )
        return _to_domain(record) if record is not None else None


def _to_record(operation: ReprocessingOperation) -> ReprocessingOperationRecord:
    return ReprocessingOperationRecord(
        id=operation.id,
        document_id=operation.document_id,
        source_run_id=operation.source_run_id,
        replacement_run_id=operation.replacement_run_id,
        requested_by=operation.requested_by,
        reason=operation.reason,
        idempotency_key=operation.idempotency_key,
        request_fingerprint=operation.request_fingerprint,
        requested_at=operation.requested_at,
    )


def _to_domain(record: ReprocessingOperationRecord) -> ReprocessingOperation:
    return ReprocessingOperation(
        id=record.id,
        document_id=record.document_id,
        source_run_id=record.source_run_id,
        replacement_run_id=record.replacement_run_id,
        requested_by=record.requested_by,
        reason=record.reason,
        idempotency_key=record.idempotency_key,
        request_fingerprint=record.request_fingerprint,
        requested_at=record.requested_at,
    )
