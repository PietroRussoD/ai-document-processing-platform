"""SQLAlchemy document-status read model."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from document_platform.adapters.outbound.postgresql.models import (
    DocumentClassificationRecord,
    DocumentOcrExtractionRecord,
    DocumentRecord,
    DocumentTextExtractionRecord,
    DocumentTextSelectionRecord,
    InvoiceExtractionRecord,
    InvoiceReviewCorrectionRecord,
    InvoiceValidationRecord,
    ProcessingRunRecord,
    ReviewResolutionRecord,
)
from document_platform.application.ports import (
    ClassificationMetadataView,
    DocumentStatusView,
    InvoiceExtractionMetadataView,
    InvoiceReviewCorrectionMetadataView,
    InvoiceValidationMetadataView,
    OcrExtractionMetadataView,
    ProcessingFailureMetadataView,
    ProcessingOutputView,
    ProcessingRunStatusView,
    ReviewResolutionMetadataView,
    TextExtractionMetadataView,
    TextSelectionMetadataView,
)
from document_platform.domain.documents import DocumentStatus
from document_platform.domain.processing import (
    BusinessDocumentType,
    DocumentClassificationReason,
    EmbeddedTextQuality,
    InvoiceExtractionMethod,
    InvoiceReviewField,
    InvoiceValidationDecision,
    InvoiceValidationIssue,
    OcrExtractionMethod,
    ProcessingFailureCode,
    ProcessingRunStatus,
    ProcessingStage,
    ProcessingTextSelectionReason,
    ProcessingTextSource,
    ReviewResolutionDecision,
    TextExtractionMethod,
)


class SqlAlchemyDocumentStatusReader:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get(self, document_id: UUID) -> DocumentStatusView | None:
        statement = (
            select(
                DocumentRecord,
                ProcessingRunRecord,
                DocumentTextExtractionRecord,
                DocumentOcrExtractionRecord,
                DocumentTextSelectionRecord,
                DocumentClassificationRecord,
                InvoiceExtractionRecord,
                InvoiceValidationRecord,
                ReviewResolutionRecord,
            )
            .join(ProcessingRunRecord, ProcessingRunRecord.document_id == DocumentRecord.id)
            .outerjoin(
                DocumentTextExtractionRecord,
                DocumentTextExtractionRecord.processing_run_id == ProcessingRunRecord.id,
            )
            .outerjoin(
                DocumentOcrExtractionRecord,
                DocumentOcrExtractionRecord.processing_run_id == ProcessingRunRecord.id,
            )
            .outerjoin(
                DocumentTextSelectionRecord,
                DocumentTextSelectionRecord.processing_run_id == ProcessingRunRecord.id,
            )
            .outerjoin(
                DocumentClassificationRecord,
                DocumentClassificationRecord.processing_run_id == ProcessingRunRecord.id,
            )
            .outerjoin(
                InvoiceExtractionRecord,
                InvoiceExtractionRecord.processing_run_id == ProcessingRunRecord.id,
            )
            .outerjoin(
                InvoiceValidationRecord,
                InvoiceValidationRecord.processing_run_id == ProcessingRunRecord.id,
            )
            .outerjoin(
                ReviewResolutionRecord,
                ReviewResolutionRecord.processing_run_id == ProcessingRunRecord.id,
            )
            .where(DocumentRecord.id == document_id)
            .order_by(ProcessingRunRecord.queued_at.desc(), ProcessingRunRecord.id.desc())
            .limit(1)
        )
        async with self._sessions() as session:
            row = (await session.execute(statement)).one_or_none()
            correction_records = (
                (
                    await session.scalars(
                        select(InvoiceReviewCorrectionRecord)
                        .where(InvoiceReviewCorrectionRecord.processing_run_id == row[1].id)
                        .order_by(InvoiceReviewCorrectionRecord.field)
                    )
                ).all()
                if row is not None
                else ()
            )

        if row is None:
            return None

        document = row[0]
        run = row[1]
        embedded_text = row[2]
        ocr_text = row[3]
        selected_text = row[4]
        classification = row[5]
        invoice_extraction = row[6]
        invoice_validation = row[7]
        review_resolution = row[8]
        return DocumentStatusView(
            id=document.id,
            original_filename=document.original_filename,
            media_type=document.media_type,
            size_bytes=document.size_bytes,
            page_count=document.page_count,
            content_sha256=document.content_sha256,
            status=DocumentStatus(document.status),
            accepted_at=document.accepted_at,
            status_changed_at=document.status_changed_at,
            current_run=ProcessingRunStatusView(
                id=run.id,
                previous_run_id=run.previous_run_id,
                status=ProcessingRunStatus(run.status),
                queued_at=run.queued_at,
                started_at=run.started_at,
                status_changed_at=run.status_changed_at,
                finished_at=run.finished_at,
                attempt_count=run.attempt_count,
                failure=(
                    ProcessingFailureMetadataView(
                        stage=ProcessingStage(run.failure_stage),
                        code=ProcessingFailureCode(run.failure_code),
                    )
                    if run.failure_stage is not None and run.failure_code is not None
                    else None
                ),
                processing_output=_to_processing_output(
                    embedded_text=embedded_text,
                    ocr_text=ocr_text,
                    selected_text=selected_text,
                    classification=classification,
                    invoice_extraction=invoice_extraction,
                    invoice_validation=invoice_validation,
                ),
                review_resolution=(
                    ReviewResolutionMetadataView(
                        decision=ReviewResolutionDecision(review_resolution.decision),
                        reviewer_id=review_resolution.reviewer_id,
                        review_note=review_resolution.review_note,
                        resolved_at=review_resolution.resolved_at,
                        corrections=tuple(
                            _to_review_correction_metadata(record) for record in correction_records
                        ),
                    )
                    if review_resolution is not None
                    else None
                ),
            ),
        )


def _to_processing_output(
    *,
    embedded_text: DocumentTextExtractionRecord | None,
    ocr_text: DocumentOcrExtractionRecord | None,
    selected_text: DocumentTextSelectionRecord | None,
    classification: DocumentClassificationRecord | None,
    invoice_extraction: InvoiceExtractionRecord | None,
    invoice_validation: InvoiceValidationRecord | None,
) -> ProcessingOutputView | None:
    if all(
        value is None
        for value in (
            embedded_text,
            ocr_text,
            selected_text,
            classification,
            invoice_extraction,
            invoice_validation,
        )
    ):
        return None
    return ProcessingOutputView(
        embedded_text=(
            TextExtractionMetadataView(
                method=TextExtractionMethod(embedded_text.method),
                quality=EmbeddedTextQuality(embedded_text.quality),
                page_count=embedded_text.page_count,
                character_count=embedded_text.character_count,
                non_whitespace_character_count=embedded_text.non_whitespace_character_count,
                extracted_at=embedded_text.extracted_at,
            )
            if embedded_text is not None
            else None
        ),
        ocr_text=(
            OcrExtractionMetadataView(
                method=OcrExtractionMethod(ocr_text.method),
                page_count=ocr_text.page_count,
                character_count=ocr_text.character_count,
                non_whitespace_character_count=ocr_text.non_whitespace_character_count,
                extracted_at=ocr_text.extracted_at,
            )
            if ocr_text is not None
            else None
        ),
        selected_text=(
            TextSelectionMetadataView(
                source=ProcessingTextSource(selected_text.source),
                reason=ProcessingTextSelectionReason(selected_text.reason),
                selected_at=selected_text.selected_at,
            )
            if selected_text is not None
            else None
        ),
        classification=(
            ClassificationMetadataView(
                document_type=BusinessDocumentType(classification.document_type),
                reason=DocumentClassificationReason(classification.reason),
                classified_at=classification.classified_at,
            )
            if classification is not None
            else None
        ),
        invoice_extraction=(
            InvoiceExtractionMetadataView(
                method=InvoiceExtractionMethod(invoice_extraction.method),
                invoice_number=invoice_extraction.invoice_number,
                issue_date=invoice_extraction.issue_date,
                supplier_name=invoice_extraction.supplier_name,
                currency=invoice_extraction.currency,
                total_amount=invoice_extraction.total_amount,
                extracted_at=invoice_extraction.extracted_at,
            )
            if invoice_extraction is not None
            else None
        ),
        invoice_validation=(
            InvoiceValidationMetadataView(
                decision=InvoiceValidationDecision(invoice_validation.decision),
                issues=tuple(InvoiceValidationIssue(issue) for issue in invoice_validation.issues),
                validated_at=invoice_validation.validated_at,
            )
            if invoice_validation is not None
            else None
        ),
    )


def _to_review_correction_metadata(
    record: InvoiceReviewCorrectionRecord,
) -> InvoiceReviewCorrectionMetadataView:
    field = InvoiceReviewField(record.field)
    if field is InvoiceReviewField.ISSUE_DATE:
        if record.corrected_date is None:
            raise RuntimeError("persisted ISSUE_DATE correction is missing corrected_date")
        value = record.corrected_date
    elif field is InvoiceReviewField.TOTAL_AMOUNT:
        if record.corrected_amount is None:
            raise RuntimeError("persisted TOTAL_AMOUNT correction is missing corrected_amount")
        value = record.corrected_amount
    else:
        if record.corrected_text is None:
            raise RuntimeError("persisted text correction is missing corrected_text")
        value = record.corrected_text
    return InvoiceReviewCorrectionMetadataView(
        field=field,
        corrected_value=value,
        corrected_at=record.corrected_at,
    )
