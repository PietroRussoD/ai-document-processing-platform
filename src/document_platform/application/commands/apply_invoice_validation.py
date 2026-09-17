"""Apply a persisted invoice-validation decision to a document lifecycle."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from document_platform.application.ports import Clock, UnitOfWorkFactory
from document_platform.domain.documents import DocumentStatus
from document_platform.domain.processing import InvoiceValidationDecision, ProcessingRunStatus


@dataclass(frozen=True, slots=True)
class ApplyInvoiceValidation:
    processing_run_id: UUID


@dataclass(frozen=True, slots=True)
class InvoiceValidationApplied:
    processing_run_id: UUID
    decision: InvoiceValidationDecision
    applied_at: datetime
    replayed: bool


class InvoiceValidationApplicationRequiresValidation(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"invoice validation is missing: {processing_run_id}")


class InvoiceValidationApplicationRunNotFound(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"processing run not found: {processing_run_id}")


class InvoiceValidationApplicationDocumentNotFound(RuntimeError):
    def __init__(self, processing_run_id: UUID, document_id: UUID) -> None:
        super().__init__(
            f"document not found for processing run {processing_run_id}: {document_id}"
        )


class InvalidInvoiceValidationApplication(RuntimeError):
    def __init__(
        self,
        *,
        processing_run_id: UUID,
        run_status: ProcessingRunStatus,
        document_status: DocumentStatus,
    ) -> None:
        super().__init__(
            "invoice validation cannot be applied from "
            f"run={run_status}, document={document_status}: {processing_run_id}"
        )


class ApplyInvoiceValidationHandler:
    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def __call__(self, command: ApplyInvoiceValidation) -> InvoiceValidationApplied:
        async with self._unit_of_work_factory() as unit_of_work:
            validation = await unit_of_work.invoice_validations.get(command.processing_run_id)
            if validation is None:
                raise InvoiceValidationApplicationRequiresValidation(command.processing_run_id)
            run = await unit_of_work.processing_runs.get(command.processing_run_id)
            if run is None:
                raise InvoiceValidationApplicationRunNotFound(command.processing_run_id)
            document = await unit_of_work.documents.get(run.document_id)
            if document is None:
                raise InvoiceValidationApplicationDocumentNotFound(run.id, run.document_id)

            if _is_replay(validation.decision, run.status, document.status):
                return InvoiceValidationApplied(
                    processing_run_id=run.id,
                    decision=validation.decision,
                    applied_at=run.status_changed_at,
                    replayed=True,
                )
            if (
                run.status is not ProcessingRunStatus.RUNNING
                or document.status is not DocumentStatus.PROCESSING
            ):
                raise InvalidInvoiceValidationApplication(
                    processing_run_id=run.id,
                    run_status=run.status,
                    document_status=document.status,
                )

            applied_at = self._clock()
            if validation.decision is InvoiceValidationDecision.AUTO_APPROVE:
                updated_document = document.approve(at=applied_at)
                updated_run = run.complete(at=applied_at)
            else:
                updated_document = document.require_review(at=applied_at)
                updated_run = run.require_review(at=applied_at)
            await unit_of_work.documents.update(updated_document)
            await unit_of_work.processing_runs.update(updated_run)
            await unit_of_work.commit()
            return InvoiceValidationApplied(
                processing_run_id=run.id,
                decision=validation.decision,
                applied_at=applied_at,
                replayed=False,
            )


def _is_replay(
    decision: InvoiceValidationDecision,
    run_status: ProcessingRunStatus,
    document_status: DocumentStatus,
) -> bool:
    if decision is InvoiceValidationDecision.AUTO_APPROVE:
        return (
            run_status is ProcessingRunStatus.COMPLETED
            and document_status is DocumentStatus.APPROVED
        )
    return (
        run_status is ProcessingRunStatus.REVIEW_REQUIRED
        and document_status is DocumentStatus.REVIEW_REQUIRED
    )
