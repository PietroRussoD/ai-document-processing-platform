"""PostgreSQL reference checks for content-addressed blobs."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import PostgresDsn
from sqlalchemy import delete

from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.adapters.outbound.postgresql.models import DocumentRecord
from document_platform.adapters.outbound.postgresql.queries import SqlAlchemyBlobReferenceReader
from document_platform.adapters.outbound.postgresql.repositories import SqlAlchemyDocumentRepository
from document_platform.application.ports import BlobIdentity
from document_platform.domain.documents import Document
from document_platform.settings import Settings


@pytest.mark.anyio
async def test_blob_remains_referenced_until_its_last_document_is_deleted(
    migrated_postgres_url: str,
) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    digest = uuid4().hex * 2
    key = f"blobs/sha256/{digest[:2]}/{digest}"
    document_ids = (uuid4(), uuid4())
    reader = SqlAlchemyBlobReferenceReader(database.sessions)
    try:
        async with database.sessions.begin() as session:
            repository = SqlAlchemyDocumentRepository(session)
            for document_id in document_ids:
                await repository.add(
                    Document.accept_pdf(
                        document_id=document_id,
                        original_filename="shared.pdf",
                        size_bytes=100,
                        page_count=1,
                        content_sha256=digest,
                        storage_key=key,
                        accepted_at=datetime(2026, 9, 24, tzinfo=UTC),
                    )
                )

        assert await reader.is_referenced(key=key, content_sha256=digest)
        assert await reader.find_referenced(
            {BlobIdentity(key, digest), BlobIdentity("blobs/sha256/00/other", digest)}
        ) == frozenset({BlobIdentity(key, digest)})
        assert not await reader.is_referenced(
            key=f"blobs/sha256/{digest[:2]}/other", content_sha256=digest
        )

        async with database.sessions.begin() as session:
            await session.execute(
                delete(DocumentRecord).where(DocumentRecord.id == document_ids[0])
            )
        assert await reader.is_referenced(key=key, content_sha256=digest)

        async with database.sessions.begin() as session:
            await session.execute(
                delete(DocumentRecord).where(DocumentRecord.id == document_ids[1])
            )
        assert not await reader.is_referenced(key=key, content_sha256=digest)
        assert await reader.find_referenced({BlobIdentity(key, digest)}) == frozenset()
    finally:
        await database.dispose()
