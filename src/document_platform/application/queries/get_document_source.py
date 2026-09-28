"""Retrieve the original PDF for an authenticated local review."""

from uuid import UUID

from document_platform.application.ports import (
    BlobNotFound,
    BlobStore,
    BlobTooLarge,
    DocumentSourceReader,
)
from document_platform.application.queries.get_document_status import DocumentNotFound


class DocumentSourceUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("source document is unavailable")


class GetDocumentSourceHandler:
    def __init__(self, reader: DocumentSourceReader, blob_store: BlobStore) -> None:
        self._reader = reader
        self._blob_store = blob_store

    async def __call__(self, document_id: UUID) -> bytes:
        storage_key = await self._reader.get_storage_key(document_id)
        if storage_key is None:
            raise DocumentNotFound(document_id)

        try:
            return await self._blob_store.load(storage_key)
        except (BlobNotFound, BlobTooLarge) as error:
            raise DocumentSourceUnavailable from error
