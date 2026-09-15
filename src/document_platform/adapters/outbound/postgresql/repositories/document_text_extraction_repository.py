"""SQLAlchemy repository for immutable document text extractions."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from document_platform.adapters.outbound.postgresql.errors import is_unique_violation
from document_platform.adapters.outbound.postgresql.models import DocumentTextExtractionRecord
from document_platform.application.ports import DocumentTextExtractionAlreadyExists
from document_platform.domain.processing import DocumentTextExtraction, TextExtractionMethod


class SqlAlchemyDocumentTextExtractionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, extraction: DocumentTextExtraction) -> None:
        self._session.add(_to_record(extraction))
        try:
            await self._session.flush()
        except IntegrityError as error:
            if is_unique_violation(error):
                raise DocumentTextExtractionAlreadyExists(extraction.processing_run_id) from error
            raise

    async def get(self, processing_run_id: UUID) -> DocumentTextExtraction | None:
        record = await self._session.get(DocumentTextExtractionRecord, processing_run_id)
        return _to_domain(record) if record is not None else None


def _to_record(extraction: DocumentTextExtraction) -> DocumentTextExtractionRecord:
    return DocumentTextExtractionRecord(
        processing_run_id=extraction.processing_run_id,
        method=extraction.method.value,
        text=extraction.text,
        page_count=extraction.page_count,
        character_count=extraction.character_count,
        non_whitespace_character_count=extraction.non_whitespace_character_count,
        extracted_at=extraction.extracted_at,
    )


def _to_domain(record: DocumentTextExtractionRecord) -> DocumentTextExtraction:
    return DocumentTextExtraction(
        processing_run_id=record.processing_run_id,
        method=TextExtractionMethod(record.method),
        text=record.text,
        page_count=record.page_count,
        character_count=record.character_count,
        non_whitespace_character_count=record.non_whitespace_character_count,
        extracted_at=record.extracted_at,
    )
