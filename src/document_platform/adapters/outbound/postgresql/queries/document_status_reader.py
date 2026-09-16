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
    ProcessingRunRecord,
)
from document_platform.application.ports import (
    ClassificationMetadataView,
    DocumentStatusView,
    OcrExtractionMetadataView,
    ProcessingOutputView,
    ProcessingRunStatusView,
    TextExtractionMetadataView,
    TextSelectionMetadataView,
)
from document_platform.domain.documents import DocumentStatus
from document_platform.domain.processing import (
    BusinessDocumentType,
    DocumentClassificationReason,
    EmbeddedTextQuality,
    OcrExtractionMethod,
    ProcessingRunStatus,
    ProcessingTextSelectionReason,
    ProcessingTextSource,
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
            .where(DocumentRecord.id == document_id)
            .order_by(ProcessingRunRecord.queued_at.desc(), ProcessingRunRecord.id.desc())
            .limit(1)
        )
        async with self._sessions() as session:
            row = (await session.execute(statement)).one_or_none()

        if row is None:
            return None

        document = row[0]
        run = row[1]
        embedded_text = row[2]
        ocr_text = row[3]
        selected_text = row[4]
        classification = row[5]
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
                status=ProcessingRunStatus(run.status),
                queued_at=run.queued_at,
                started_at=run.started_at,
                status_changed_at=run.status_changed_at,
                finished_at=run.finished_at,
                attempt_count=run.attempt_count,
                processing_output=_to_processing_output(
                    embedded_text=embedded_text,
                    ocr_text=ocr_text,
                    selected_text=selected_text,
                    classification=classification,
                ),
            ),
        )


def _to_processing_output(
    *,
    embedded_text: DocumentTextExtractionRecord | None,
    ocr_text: DocumentOcrExtractionRecord | None,
    selected_text: DocumentTextSelectionRecord | None,
    classification: DocumentClassificationRecord | None,
) -> ProcessingOutputView | None:
    if all(value is None for value in (embedded_text, ocr_text, selected_text, classification)):
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
    )
