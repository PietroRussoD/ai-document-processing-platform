"""Application tests for manual review resolution."""

from datetime import UTC, datetime
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from document_platform.application.commands.resolve_document_review import (
    ConflictingReviewResolution,
    DocumentReviewResolved,
    ResolveDocumentReview,
    ResolveDocumentReviewHandler,
)
from document_platform.application.ports import UnitOfWork
from document_platform.domain.documents import Document, DocumentStatus
from document_platform.domain.processing import (
    ProcessingRun,
    ProcessingRunStatus,
    ReviewResolution,
    ReviewResolutionDecision,
)

QUEUED_AT = datetime(2026, 9, 17, 15, 0, tzinfo=UTC)
REVIEWED_AT = datetime(2026, 9, 17, 15, 1, tzinfo=UTC)
RESOLVED_AT = datetime(2026, 9, 17, 15, 2, tzinfo=UTC)
DOCUMENT_ID = UUID("f8f8f8f8-f8f8-48f8-88f8-f8f8f8f8f8f8")
RUN_ID = UUID("f9f9f9f9-f9f9-49f9-89f9-f9f9f9f9f9f9")
REVIEWER_ID = "operator-42"


class ValueRepository:
    def __init__(self, value: object | None = None) -> None:
        self.value = value
        self.updated: list[object] = []

    async def get(self, identifier: UUID) -> object | None:
        return self.value

    async def add(self, value: object) -> None:
        self.value = value

    async def update(self, value: object) -> None:
        self.value = value
        self.updated.append(value)


class RecordingUnitOfWork:
    def __init__(self) -> None:
        self.documents = ValueRepository(review_required_document())
        self.processing_runs = ValueRepository(review_required_run())
        self.review_resolutions = ValueRepository()
        self.commit_count = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.commit_count += 1


def review_required_document() -> Document:
    return (
        Document.accept_pdf(
            document_id=DOCUMENT_ID,
            original_filename="invoice.pdf",
            size_bytes=10_000,
            page_count=1,
            content_sha256=DOCUMENT_ID.hex * 2,
            storage_key=f"blobs/{DOCUMENT_ID}",
            accepted_at=QUEUED_AT,
        )
        .start_processing(at=REVIEWED_AT)
        .require_review(at=REVIEWED_AT)
    )


def review_required_run() -> ProcessingRun:
    return (
        ProcessingRun.queue(run_id=RUN_ID, document_id=DOCUMENT_ID, queued_at=QUEUED_AT)
        .start(at=REVIEWED_AT)
        .require_review(at=REVIEWED_AT)
    )


def handler(unit_of_work: RecordingUnitOfWork) -> ResolveDocumentReviewHandler:
    return ResolveDocumentReviewHandler(
        unit_of_work_factory=lambda: cast(UnitOfWork, unit_of_work),
        clock=lambda: RESOLVED_AT,
    )


def command(decision: ReviewResolutionDecision) -> ResolveDocumentReview:
    return ResolveDocumentReview(
        processing_run_id=RUN_ID,
        decision=decision,
        reviewer_id=REVIEWER_ID,
        review_note="Reviewed against the supplier record.",
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("decision", "expected_document_status"),
    [
        (ReviewResolutionDecision.APPROVE, DocumentStatus.APPROVED),
        (ReviewResolutionDecision.REJECT, DocumentStatus.REJECTED),
    ],
)
async def test_persists_resolution_and_completes_review_atomically(
    decision: ReviewResolutionDecision,
    expected_document_status: DocumentStatus,
) -> None:
    unit_of_work = RecordingUnitOfWork()

    result = await handler(unit_of_work)(command(decision))

    assert result == DocumentReviewResolved(
        RUN_ID, decision, REVIEWER_ID, RESOLVED_AT, replayed=False
    )
    assert cast(Document, unit_of_work.documents.updated[0]).status is expected_document_status
    assert (
        cast(ProcessingRun, unit_of_work.processing_runs.updated[0]).status
        is ProcessingRunStatus.COMPLETED
    )
    assert cast(ReviewResolution, unit_of_work.review_resolutions.value).decision is decision
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_replays_the_same_resolution_without_mutation() -> None:
    unit_of_work = RecordingUnitOfWork()
    unit_of_work.documents.value = review_required_document().approve(at=RESOLVED_AT)
    unit_of_work.processing_runs.value = review_required_run().complete_after_review(at=RESOLVED_AT)
    unit_of_work.review_resolutions.value = ReviewResolution(
        processing_run_id=RUN_ID,
        decision=ReviewResolutionDecision.APPROVE,
        reviewer_id=REVIEWER_ID,
        review_note="Reviewed against the supplier record.",
        resolved_at=RESOLVED_AT,
    )

    result = await handler(unit_of_work)(command(ReviewResolutionDecision.APPROVE))

    assert result.replayed is True
    assert unit_of_work.documents.updated == []
    assert unit_of_work.processing_runs.updated == []
    assert unit_of_work.commit_count == 0


@pytest.mark.anyio
async def test_rejects_a_conflicting_second_resolution() -> None:
    unit_of_work = RecordingUnitOfWork()
    unit_of_work.documents.value = review_required_document().approve(at=RESOLVED_AT)
    unit_of_work.processing_runs.value = review_required_run().complete_after_review(at=RESOLVED_AT)
    unit_of_work.review_resolutions.value = ReviewResolution(
        processing_run_id=RUN_ID,
        decision=ReviewResolutionDecision.APPROVE,
        reviewer_id=REVIEWER_ID,
        review_note="Reviewed against the supplier record.",
        resolved_at=RESOLVED_AT,
    )

    with pytest.raises(ConflictingReviewResolution):
        await handler(unit_of_work)(command(ReviewResolutionDecision.REJECT))
