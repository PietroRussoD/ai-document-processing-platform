"""Invoice-validation application tests."""

from datetime import UTC, datetime
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from document_platform.application.commands.apply_invoice_validation import (
    ApplyInvoiceValidation,
    ApplyInvoiceValidationHandler,
    InvoiceValidationApplicationRequiresValidation,
    InvoiceValidationApplied,
)
from document_platform.application.ports import UnitOfWork
from document_platform.domain.documents import Document, DocumentStatus
from document_platform.domain.processing import (
    InvoiceValidation,
    InvoiceValidationDecision,
    InvoiceValidationIssue,
    ProcessingRun,
    ProcessingRunStatus,
)

QUEUED_AT = datetime(2026, 9, 17, 11, 0, tzinfo=UTC)
STARTED_AT = datetime(2026, 9, 17, 11, 1, tzinfo=UTC)
APPLIED_AT = datetime(2026, 9, 17, 11, 2, tzinfo=UTC)
DOCUMENT_ID = UUID("e8e8e8e8-e8e8-48e8-88e8-e8e8e8e8e8e8")
RUN_ID = UUID("e9e9e9e9-e9e9-49e9-89e9-e9e9e9e9e9e9")


class ValueRepository:
    def __init__(self, value: object | None = None) -> None:
        self.value = value
        self.updated: list[object] = []

    async def get(self, identifier: UUID) -> object | None:
        return self.value

    async def update(self, value: object) -> None:
        self.value = value
        self.updated.append(value)


class RecordingUnitOfWork:
    def __init__(self, decision: InvoiceValidationDecision) -> None:
        self.documents = ValueRepository(processing_document())
        self.processing_runs = ValueRepository(running_run())
        self.invoice_validations = ValueRepository(
            InvoiceValidation(
                processing_run_id=RUN_ID,
                decision=decision,
                issues=(InvoiceValidationIssue.MISSING_TOTAL_AMOUNT,)
                if decision is InvoiceValidationDecision.REVIEW_REQUIRED
                else (),
                validated_at=STARTED_AT,
            )
        )
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


def processing_document() -> Document:
    return Document.accept_pdf(
        document_id=DOCUMENT_ID,
        original_filename="invoice.pdf",
        size_bytes=10_000,
        page_count=1,
        content_sha256=DOCUMENT_ID.hex * 2,
        storage_key=f"blobs/{DOCUMENT_ID}",
        accepted_at=QUEUED_AT,
    ).start_processing(at=STARTED_AT)


def running_run() -> ProcessingRun:
    return ProcessingRun.queue(
        run_id=RUN_ID,
        document_id=DOCUMENT_ID,
        queued_at=QUEUED_AT,
    ).start(at=STARTED_AT)


def handler(unit_of_work: RecordingUnitOfWork) -> ApplyInvoiceValidationHandler:
    return ApplyInvoiceValidationHandler(
        unit_of_work_factory=lambda: cast(UnitOfWork, unit_of_work),
        clock=lambda: APPLIED_AT,
    )


@pytest.mark.anyio
async def test_approves_document_and_completes_run_atomically() -> None:
    unit_of_work = RecordingUnitOfWork(InvoiceValidationDecision.AUTO_APPROVE)

    result = await handler(unit_of_work)(ApplyInvoiceValidation(RUN_ID))

    assert result == InvoiceValidationApplied(
        RUN_ID,
        InvoiceValidationDecision.AUTO_APPROVE,
        APPLIED_AT,
        replayed=False,
    )
    document = cast(Document, unit_of_work.documents.updated[0])
    run = cast(ProcessingRun, unit_of_work.processing_runs.updated[0])
    assert document.status is DocumentStatus.APPROVED
    assert run.status is ProcessingRunStatus.COMPLETED
    assert run.finished_at == APPLIED_AT
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_routes_an_incomplete_invoice_to_review() -> None:
    unit_of_work = RecordingUnitOfWork(InvoiceValidationDecision.REVIEW_REQUIRED)
    unit_of_work.invoice_validations.value = InvoiceValidation(
        processing_run_id=RUN_ID,
        decision=InvoiceValidationDecision.REVIEW_REQUIRED,
        issues=(InvoiceValidationIssue.MISSING_TOTAL_AMOUNT,),
        validated_at=STARTED_AT,
    )

    result = await handler(unit_of_work)(ApplyInvoiceValidation(RUN_ID))

    assert result == InvoiceValidationApplied(
        RUN_ID,
        InvoiceValidationDecision.REVIEW_REQUIRED,
        APPLIED_AT,
        replayed=False,
    )
    document = cast(Document, unit_of_work.documents.updated[0])
    run = cast(ProcessingRun, unit_of_work.processing_runs.updated[0])
    assert document.status is DocumentStatus.REVIEW_REQUIRED
    assert run.status is ProcessingRunStatus.REVIEW_REQUIRED
    assert run.finished_at is None


@pytest.mark.anyio
async def test_replay_does_not_repeat_an_applied_approval() -> None:
    unit_of_work = RecordingUnitOfWork(InvoiceValidationDecision.AUTO_APPROVE)
    unit_of_work.documents.value = processing_document().approve(at=APPLIED_AT)
    unit_of_work.processing_runs.value = running_run().complete(at=APPLIED_AT)

    result = await handler(unit_of_work)(ApplyInvoiceValidation(RUN_ID))

    assert result == InvoiceValidationApplied(
        RUN_ID,
        InvoiceValidationDecision.AUTO_APPROVE,
        APPLIED_AT,
        replayed=True,
    )
    assert unit_of_work.documents.updated == []
    assert unit_of_work.processing_runs.updated == []
    assert unit_of_work.commit_count == 0


@pytest.mark.anyio
async def test_requires_a_persisted_validation() -> None:
    unit_of_work = RecordingUnitOfWork(InvoiceValidationDecision.AUTO_APPROVE)
    unit_of_work.invoice_validations.value = None

    with pytest.raises(InvoiceValidationApplicationRequiresValidation):
        await handler(unit_of_work)(ApplyInvoiceValidation(RUN_ID))
