"""Resolve a durable processing-review handoff exactly once."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from document_platform.application.ports import Clock, UnitOfWork, UnitOfWorkFactory
from document_platform.domain.documents import DocumentStatus
from document_platform.domain.processing import (
    InvoiceExtraction,
    InvoiceReviewCorrection,
    InvoiceReviewField,
    InvoiceReviewFieldCorrection,
    InvoiceValidationDecision,
    InvoiceValidationIssue,
    InvoiceValidationPolicy,
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
    corrections: tuple[InvoiceReviewFieldCorrection, ...] = ()


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


class ReviewResolutionRequiresInvoiceExtraction(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"review approval requires invoice extraction: {processing_run_id}")


class ReviewApprovalRequiresCompleteInvoice(RuntimeError):
    def __init__(self, issues: tuple[InvoiceValidationIssue, ...]) -> None:
        super().__init__("review approval requires a complete corrected invoice")
        self.issues = issues


class ReviewCorrectionRequiresApproval(ValueError):
    """Raised when an operator submits field changes while rejecting a review."""


class ResolveDocumentReviewHandler:
    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        clock: Clock,
        invoice_validation_policy: InvoiceValidationPolicy | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._invoice_validation_policy = invoice_validation_policy or InvoiceValidationPolicy()

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
                existing_correction = await unit_of_work.invoice_review_corrections.get(run.id)
                if not _matches(command, existing, existing_correction):
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
            correction = await self._validate_corrections(
                command=command,
                unit_of_work=unit_of_work,
                resolved_at=resolved_at,
            )
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
            if correction is not None:
                await unit_of_work.invoice_review_corrections.add(correction)
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

    async def _validate_corrections(
        self,
        *,
        command: ResolveDocumentReview,
        unit_of_work: UnitOfWork,
        resolved_at: datetime,
    ) -> InvoiceReviewCorrection | None:
        if command.decision is ReviewResolutionDecision.REJECT:
            if command.corrections:
                raise ReviewCorrectionRequiresApproval(
                    "invoice corrections require an APPROVE review decision"
                )
            return None

        extraction = await unit_of_work.invoice_extractions.get(command.processing_run_id)
        if extraction is None:
            raise ReviewResolutionRequiresInvoiceExtraction(command.processing_run_id)
        corrected = _apply_corrections(extraction, command.corrections)
        validation = self._invoice_validation_policy.validate(
            extraction=corrected,
            validated_at=resolved_at,
        )
        if validation.decision is not InvoiceValidationDecision.AUTO_APPROVE:
            raise ReviewApprovalRequiresCompleteInvoice(validation.issues)
        return (
            InvoiceReviewCorrection(
                processing_run_id=command.processing_run_id,
                corrections=command.corrections,
                corrected_at=resolved_at,
            )
            if command.corrections
            else None
        )


def _matches(
    command: ResolveDocumentReview,
    resolution: ReviewResolution,
    correction: InvoiceReviewCorrection | None,
) -> bool:
    return (
        command.decision is resolution.decision
        and command.reviewer_id == resolution.reviewer_id
        and command.review_note == resolution.review_note
        and _corrections_match(command.corrections, correction)
    )


def _corrections_match(
    expected: tuple[InvoiceReviewFieldCorrection, ...],
    actual: InvoiceReviewCorrection | None,
) -> bool:
    return frozenset(expected) == frozenset(actual.corrections if actual is not None else ())


def _apply_corrections(
    extraction: InvoiceExtraction,
    corrections: tuple[InvoiceReviewFieldCorrection, ...],
) -> InvoiceExtraction:
    invoice_number = extraction.invoice_number
    issue_date = extraction.issue_date
    supplier_name = extraction.supplier_name
    currency = extraction.currency
    total_amount = extraction.total_amount
    for correction in corrections:
        value = correction.corrected_value
        if correction.field is InvoiceReviewField.INVOICE_NUMBER:
            invoice_number = _require_text_correction(correction.field, value)
        elif correction.field is InvoiceReviewField.ISSUE_DATE:
            issue_date = _require_date_correction(correction.field, value)
        elif correction.field is InvoiceReviewField.SUPPLIER_NAME:
            supplier_name = _require_text_correction(correction.field, value)
        elif correction.field is InvoiceReviewField.CURRENCY:
            currency = _require_text_correction(correction.field, value)
        elif correction.field is InvoiceReviewField.TOTAL_AMOUNT:
            total_amount = _require_amount_correction(correction.field, value)
    return InvoiceExtraction(
        processing_run_id=extraction.processing_run_id,
        method=extraction.method,
        invoice_number=invoice_number,
        issue_date=issue_date,
        supplier_name=supplier_name,
        currency=currency,
        total_amount=total_amount,
        extracted_at=extraction.extracted_at,
    )


def _require_text_correction(
    field: InvoiceReviewField,
    value: object,
) -> str:
    if not isinstance(value, str):
        raise RuntimeError(f"persisted {field} correction has an invalid value type")
    return value


def _require_date_correction(
    field: InvoiceReviewField,
    value: object,
) -> date:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise RuntimeError(f"persisted {field} correction has an invalid value type")
    return value


def _require_amount_correction(
    field: InvoiceReviewField,
    value: object,
) -> Decimal:
    if not isinstance(value, Decimal):
        raise RuntimeError(f"persisted {field} correction has an invalid value type")
    return value


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
