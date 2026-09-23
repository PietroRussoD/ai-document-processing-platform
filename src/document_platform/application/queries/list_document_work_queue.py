"""List a bounded page from an operator work queue."""

from document_platform.application.ports import (
    DocumentWorkQueue,
    DocumentWorkQueuePage,
    DocumentWorkQueueReader,
)


class ListDocumentWorkQueueHandler:
    def __init__(self, reader: DocumentWorkQueueReader) -> None:
        self._reader = reader

    async def __call__(
        self, queue: DocumentWorkQueue, *, limit: int, offset: int
    ) -> DocumentWorkQueuePage:
        return await self._reader.list_queue(queue, limit=limit, offset=offset)
