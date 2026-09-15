"""SQLAlchemy workflow-start request repository."""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from document_platform.adapters.outbound.postgresql.errors import is_unique_violation
from document_platform.adapters.outbound.postgresql.models import WorkflowStartRequestRecord
from document_platform.application.ports import (
    ConcurrentWorkflowStartRequestUpdate,
    WorkflowStartRequestAlreadyExists,
)
from document_platform.domain.processing import WorkflowStartRequest, WorkflowStartRequestStatus


class SqlAlchemyWorkflowStartRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, request: WorkflowStartRequest) -> None:
        self._session.add(_to_record(request))
        try:
            await self._session.flush()
        except IntegrityError as error:
            if is_unique_violation(error):
                raise WorkflowStartRequestAlreadyExists(request.processing_run_id) from error
            raise

    async def get(self, processing_run_id: UUID) -> WorkflowStartRequest | None:
        record = await self._session.get(WorkflowStartRequestRecord, processing_run_id)
        return _to_domain(record) if record is not None else None

    async def claim_pending(
        self,
        *,
        owner: str,
        claimed_at: datetime,
        lease_duration: timedelta,
        limit: int,
        token_generator: Callable[[], UUID],
    ) -> tuple[WorkflowStartRequest, ...]:
        records = list(
            await self._session.scalars(
                select(WorkflowStartRequestRecord)
                .where(
                    or_(
                        WorkflowStartRequestRecord.status
                        == WorkflowStartRequestStatus.PENDING.value,
                        and_(
                            WorkflowStartRequestRecord.status
                            == WorkflowStartRequestStatus.DISPATCHING.value,
                            WorkflowStartRequestRecord.lease_expires_at <= claimed_at,
                        ),
                    )
                )
                .order_by(WorkflowStartRequestRecord.requested_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        claimed = tuple(
            _to_domain(record).claim(
                owner=owner,
                token=token_generator(),
                at=claimed_at,
                lease_duration=lease_duration,
            )
            for record in records
        )
        for request in claimed:
            await self.update(request)
        return claimed

    async def update(self, request: WorkflowStartRequest) -> None:
        if request.version < 1:
            raise ValueError("an updated workflow start request must have a positive version")

        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(WorkflowStartRequestRecord)
                .where(
                    WorkflowStartRequestRecord.processing_run_id == request.processing_run_id,
                    WorkflowStartRequestRecord.version == request.version - 1,
                )
                .values(
                    status=request.status.value,
                    dispatched_at=request.dispatched_at,
                    dispatch_owner=request.dispatch_owner,
                    dispatch_token=request.dispatch_token,
                    lease_expires_at=request.lease_expires_at,
                    attempt_count=request.attempt_count,
                    version=request.version,
                )
            ),
        )
        if result.rowcount != 1:
            raise ConcurrentWorkflowStartRequestUpdate(request.processing_run_id)


def _to_record(request: WorkflowStartRequest) -> WorkflowStartRequestRecord:
    return WorkflowStartRequestRecord(
        processing_run_id=request.processing_run_id,
        workflow_id=request.workflow_id,
        status=request.status.value,
        requested_at=request.requested_at,
        dispatched_at=request.dispatched_at,
        dispatch_owner=request.dispatch_owner,
        dispatch_token=request.dispatch_token,
        lease_expires_at=request.lease_expires_at,
        attempt_count=request.attempt_count,
        version=request.version,
    )


def _to_domain(record: WorkflowStartRequestRecord) -> WorkflowStartRequest:
    return WorkflowStartRequest(
        processing_run_id=record.processing_run_id,
        workflow_id=record.workflow_id,
        status=WorkflowStartRequestStatus(record.status),
        requested_at=record.requested_at,
        dispatched_at=record.dispatched_at,
        dispatch_owner=record.dispatch_owner,
        dispatch_token=record.dispatch_token,
        lease_expires_at=record.lease_expires_at,
        attempt_count=record.attempt_count,
        version=record.version,
    )
