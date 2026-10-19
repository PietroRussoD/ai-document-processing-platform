"""SQLAlchemy document repository."""

from typing import Any, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from document_platform.adapters.outbound.postgresql.errors import is_unique_violation
from document_platform.adapters.outbound.postgresql.models import DocumentRecord
from document_platform.application.ports import (
    ConcurrentDocumentUpdate,
    DocumentAlreadyExists,
)
from document_platform.domain.documents import Document, DocumentStatus


class SqlAlchemyDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, document: Document) -> None:
        self._session.add(_to_record(document))
        try:
            await self._session.flush()
        except IntegrityError as error:
            if is_unique_violation(error):
                raise DocumentAlreadyExists(document.id) from error
            raise

    async def get(self, document_id: UUID) -> Document | None:
        record = await self._session.get(DocumentRecord, document_id)
        return _to_domain(record) if record is not None else None

    async def get_for_update(self, document_id: UUID) -> Document | None:
        record = await self._session.scalar(
            select(DocumentRecord).where(DocumentRecord.id == document_id).with_for_update()
        )
        return _to_domain(record) if record is not None else None

    async def update(self, document: Document) -> None:
        if document.version < 1:
            raise ValueError("an updated document must have a positive version")

        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(DocumentRecord)
                .where(
                    DocumentRecord.id == document.id,
                    DocumentRecord.version == document.version - 1,
                )
                .values(
                    status=document.status.value,
                    status_changed_at=document.status_changed_at,
                    page_count=document.page_count,
                    version=document.version,
                )
            ),
        )
        if result.rowcount != 1:
            raise ConcurrentDocumentUpdate(document.id)


def _to_record(document: Document) -> DocumentRecord:
    return DocumentRecord(
        id=document.id,
        original_filename=document.original_filename,
        media_type=document.media_type,
        size_bytes=document.size_bytes,
        page_count=document.page_count,
        content_sha256=document.content_sha256,
        storage_key=document.storage_key,
        status=document.status.value,
        accepted_at=document.accepted_at,
        status_changed_at=document.status_changed_at,
        version=document.version,
    )


def _to_domain(record: DocumentRecord) -> Document:
    return Document(
        id=record.id,
        original_filename=record.original_filename,
        media_type=record.media_type,
        size_bytes=record.size_bytes,
        page_count=record.page_count,
        content_sha256=record.content_sha256,
        storage_key=record.storage_key,
        status=DocumentStatus(record.status),
        accepted_at=record.accepted_at,
        status_changed_at=record.status_changed_at,
        version=record.version,
    )
