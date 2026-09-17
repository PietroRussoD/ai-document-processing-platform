"""SQLAlchemy repository for immutable manual review resolutions."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from document_platform.adapters.outbound.postgresql.errors import is_unique_violation
from document_platform.adapters.outbound.postgresql.models import ReviewResolutionRecord
from document_platform.application.ports import ReviewResolutionAlreadyExists
from document_platform.domain.processing import ReviewResolution, ReviewResolutionDecision


class SqlAlchemyReviewResolutionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, resolution: ReviewResolution) -> None:
        self._session.add(_to_record(resolution))
        try:
            await self._session.flush()
        except IntegrityError as error:
            if is_unique_violation(error):
                raise ReviewResolutionAlreadyExists(resolution.processing_run_id) from error
            raise

    async def get(self, processing_run_id: UUID) -> ReviewResolution | None:
        record = await self._session.get(ReviewResolutionRecord, processing_run_id)
        return _to_domain(record) if record is not None else None


def _to_record(resolution: ReviewResolution) -> ReviewResolutionRecord:
    return ReviewResolutionRecord(
        processing_run_id=resolution.processing_run_id,
        decision=resolution.decision.value,
        review_note=resolution.review_note,
        resolved_at=resolution.resolved_at,
    )


def _to_domain(record: ReviewResolutionRecord) -> ReviewResolution:
    return ReviewResolution(
        processing_run_id=record.processing_run_id,
        decision=ReviewResolutionDecision(record.decision),
        review_note=record.review_note,
        resolved_at=record.resolved_at,
    )
