"""Retrieve the current persisted status of a document."""

from uuid import UUID

from document_platform.application.ports import DocumentStatusReader, DocumentStatusView


class DocumentNotFound(LookupError):
    def __init__(self, document_id: UUID) -> None:
        super().__init__(f"document not found: {document_id}")


class GetDocumentStatusHandler:
    def __init__(self, reader: DocumentStatusReader) -> None:
        self._reader = reader

    async def __call__(self, document_id: UUID) -> DocumentStatusView:
        document = await self._reader.get(document_id)
        if document is None:
            raise DocumentNotFound(document_id)
        return document
