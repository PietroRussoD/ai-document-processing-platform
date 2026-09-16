"""SQLAlchemy repository for immutable document classifications."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from document_platform.adapters.outbound.postgresql.errors import is_unique_violation
from document_platform.adapters.outbound.postgresql.models import DocumentClassificationRecord
from document_platform.application.ports import DocumentClassificationAlreadyExists
from document_platform.domain.processing import (
    BusinessDocumentType,
    DocumentClassification,
    DocumentClassificationReason,
)


class SqlAlchemyDocumentClassificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, classification: DocumentClassification) -> None:
        self._session.add(_to_record(classification))
        try:
            await self._session.flush()
        except IntegrityError as error:
            if is_unique_violation(error):
                raise DocumentClassificationAlreadyExists(
                    classification.processing_run_id
                ) from error
            raise

    async def get(self, processing_run_id: UUID) -> DocumentClassification | None:
        record = await self._session.get(DocumentClassificationRecord, processing_run_id)
        return _to_domain(record) if record is not None else None


def _to_record(classification: DocumentClassification) -> DocumentClassificationRecord:
    return DocumentClassificationRecord(
        processing_run_id=classification.processing_run_id,
        document_type=classification.document_type.value,
        reason=classification.reason.value,
        classified_at=classification.classified_at,
    )


def _to_domain(record: DocumentClassificationRecord) -> DocumentClassification:
    return DocumentClassification(
        processing_run_id=record.processing_run_id,
        document_type=BusinessDocumentType(record.document_type),
        reason=DocumentClassificationReason(record.reason),
        classified_at=record.classified_at,
    )
