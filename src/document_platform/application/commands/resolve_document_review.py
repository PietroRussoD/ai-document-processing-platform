"""Resolve a durable processing-review handoff exactly once."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from document_platform.application.ports import Clock, UnitOfWorkFactory
from document_platform.domain.documents import DocumentStatus
from document_platform.domain.processing import (
    ProcessingRunStatus,
    ReviewResolution,
    ReviewResolutionDecision,
)


@dataclass(frozen=True, slots=True)
class ResolveDocumentReview:
    processing_run_id: UUID
    decision: ReviewResolutionDecision
    reviewer_id: str
    review_note: str | None


@dataclass(frozen=True, slots=True)
class DocumentReviewResolved:
    processing_run_id: UUID
    decision: ReviewResolutionDecision
    reviewer_id: str
    resolved_at: datetime
    replayed: bool


class ReviewResolutionRunNotFound(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"processing run not found: {processing_run_id}")


class ReviewResolutionDocumentNotFound(RuntimeError):
    def __init__(self, processing_run_id: UUID, document_id: UUID) -> None:
        super().__init__(
            f"document not found for processing run {processing_run_id}: {document_id}"
        )


class InvalidReviewResolutionApplication(RuntimeError):
    def __init__(
        self,
        *,
        processing_run_id: UUID,
        run_status: ProcessingRunStatus,
        document_status: DocumentStatus,
    ) -> None:
        super().__init__(
            "review cannot be resolved from "
            f"run={run_status}, document={document_status}: {processing_run_id}"
        )


class ConflictingReviewResolution(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"review was already resolved differently: {processing_run_id}")


class ResolveDocumentReviewHandler:
    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def __call__(self, command: ResolveDocumentReview) -> DocumentReviewResolved:
        async with self._unit_of_work_factory() as unit_of_work:
            run = await unit_of_work.processing_runs.get(command.processing_run_id)
            if run is None:
                raise ReviewResolutionRunNotFound(command.processing_run_id)
            document = await unit_of_work.documents.get(run.document_id)
            if document is None:
                raise ReviewResolutionDocumentNotFound(run.id, run.document_id)

            existing = await unit_of_work.review_resolutions.get(run.id)
            if existing is not None:
                if not _matches(command, existing):
                    raise ConflictingReviewResolution(run.id)
                if not _is_applied(existing.decision, run.status, document.status):
                    raise InvalidReviewResolutionApplication(
                        processing_run_id=run.id,
                        run_status=run.status,
                        document_status=document.status,
                    )
                return DocumentReviewResolved(
                    processing_run_id=run.id,
                    decision=existing.decision,
                    reviewer_id=existing.reviewer_id,
                    resolved_at=existing.resolved_at,
                    replayed=True,
                )

            if (
                run.status is not ProcessingRunStatus.REVIEW_REQUIRED
                or document.status is not DocumentStatus.REVIEW_REQUIRED
            ):
                raise InvalidReviewResolutionApplication(
                    processing_run_id=run.id,
                    run_status=run.status,
                    document_status=document.status,
                )

            resolved_at = self._clock()
            resolution = ReviewResolution(
                processing_run_id=run.id,
                decision=command.decision,
                reviewer_id=command.reviewer_id,
                review_note=command.review_note,
                resolved_at=resolved_at,
            )
            updated_document = (
                document.approve(at=resolved_at)
                if command.decision is ReviewResolutionDecision.APPROVE
                else document.reject(at=resolved_at)
            )
            updated_run = run.complete_after_review(at=resolved_at)
            await unit_of_work.review_resolutions.add(resolution)
            await unit_of_work.documents.update(updated_document)
            await unit_of_work.processing_runs.update(updated_run)
            await unit_of_work.commit()
            return DocumentReviewResolved(
                processing_run_id=run.id,
                decision=resolution.decision,
                reviewer_id=resolution.reviewer_id,
                resolved_at=resolution.resolved_at,
                replayed=False,
            )


def _matches(command: ResolveDocumentReview, resolution: ReviewResolution) -> bool:
    return (
        command.decision is resolution.decision
        and command.reviewer_id == resolution.reviewer_id
        and command.review_note == resolution.review_note
    )


def _is_applied(
    decision: ReviewResolutionDecision,
    run_status: ProcessingRunStatus,
    document_status: DocumentStatus,
) -> bool:
    return run_status is ProcessingRunStatus.COMPLETED and (
        (
            decision is ReviewResolutionDecision.APPROVE
            and document_status is DocumentStatus.APPROVED
        )
        or (
            decision is ReviewResolutionDecision.REJECT
            and document_status is DocumentStatus.REJECTED
        )
    )
