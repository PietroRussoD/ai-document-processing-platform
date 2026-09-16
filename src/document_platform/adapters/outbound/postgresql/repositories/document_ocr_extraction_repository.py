"""SQLAlchemy repository for immutable OCR results."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from document_platform.adapters.outbound.postgresql.errors import is_unique_violation
from document_platform.adapters.outbound.postgresql.models import DocumentOcrExtractionRecord
from document_platform.application.ports import DocumentOcrExtractionAlreadyExists
from document_platform.domain.processing import DocumentOcrExtraction, OcrExtractionMethod


class SqlAlchemyDocumentOcrExtractionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, extraction: DocumentOcrExtraction) -> None:
        self._session.add(_to_record(extraction))
        try:
            await self._session.flush()
        except IntegrityError as error:
            if is_unique_violation(error):
                raise DocumentOcrExtractionAlreadyExists(extraction.processing_run_id) from error
            raise

    async def get(self, processing_run_id: UUID) -> DocumentOcrExtraction | None:
        record = await self._session.get(DocumentOcrExtractionRecord, processing_run_id)
        return _to_domain(record) if record is not None else None


def _to_record(extraction: DocumentOcrExtraction) -> DocumentOcrExtractionRecord:
    return DocumentOcrExtractionRecord(
        processing_run_id=extraction.processing_run_id,
        method=extraction.method.value,
        text=extraction.text,
        page_count=extraction.page_count,
        character_count=extraction.character_count,
        non_whitespace_character_count=extraction.non_whitespace_character_count,
        extracted_at=extraction.extracted_at,
    )


def _to_domain(record: DocumentOcrExtractionRecord) -> DocumentOcrExtraction:
    return DocumentOcrExtraction(
        processing_run_id=record.processing_run_id,
        method=OcrExtractionMethod(record.method),
        text=record.text,
        page_count=record.page_count,
        character_count=record.character_count,
        non_whitespace_character_count=record.non_whitespace_character_count,
        extracted_at=record.extracted_at,
    )
