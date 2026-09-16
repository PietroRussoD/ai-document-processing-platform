"""SQLAlchemy repository for immutable canonical-text selections."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from document_platform.adapters.outbound.postgresql.errors import is_unique_violation
from document_platform.adapters.outbound.postgresql.models import DocumentTextSelectionRecord
from document_platform.application.ports import DocumentTextSelectionAlreadyExists
from document_platform.domain.processing import (
    DocumentTextSelection,
    ProcessingTextSelectionReason,
    ProcessingTextSource,
)


class SqlAlchemyDocumentTextSelectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, selection: DocumentTextSelection) -> None:
        self._session.add(_to_record(selection))
        try:
            await self._session.flush()
        except IntegrityError as error:
            if is_unique_violation(error):
                raise DocumentTextSelectionAlreadyExists(selection.processing_run_id) from error
            raise

    async def get(self, processing_run_id: UUID) -> DocumentTextSelection | None:
        record = await self._session.get(DocumentTextSelectionRecord, processing_run_id)
        return _to_domain(record) if record is not None else None


def _to_record(selection: DocumentTextSelection) -> DocumentTextSelectionRecord:
    return DocumentTextSelectionRecord(
        processing_run_id=selection.processing_run_id,
        source=selection.source.value,
        reason=selection.reason.value,
        selected_at=selection.selected_at,
    )


def _to_domain(record: DocumentTextSelectionRecord) -> DocumentTextSelection:
    return DocumentTextSelection(
        processing_run_id=record.processing_run_id,
        source=ProcessingTextSource(record.source),
        reason=ProcessingTextSelectionReason(record.reason),
        selected_at=record.selected_at,
    )
