"""Register an already validated and durably stored PDF."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from document_platform.application.ports import Clock, IdGenerator, UnitOfWorkFactory
from document_platform.domain.documents import Document
from document_platform.domain.processing import ProcessingRun


@dataclass(frozen=True, slots=True)
class RegisterDocument:
    original_filename: str
    size_bytes: int
    page_count: int
    content_sha256: str
    storage_key: str


@dataclass(frozen=True, slots=True)
class RegisteredDocument:
    document_id: UUID
    processing_run_id: UUID
    accepted_at: datetime


class RegisterDocumentHandler:
    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        clock: Clock,
        id_generator: IdGenerator,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._id_generator = id_generator

    async def __call__(self, command: RegisterDocument) -> RegisteredDocument:
        accepted_at = self._clock()
        document = Document.accept_pdf(
            document_id=self._id_generator(),
            original_filename=command.original_filename,
            size_bytes=command.size_bytes,
            page_count=command.page_count,
            content_sha256=command.content_sha256,
            storage_key=command.storage_key,
            accepted_at=accepted_at,
        )
        processing_run = ProcessingRun.queue(
            run_id=self._id_generator(),
            document_id=document.id,
            queued_at=accepted_at,
        )

        async with self._unit_of_work_factory() as unit_of_work:
            await unit_of_work.documents.add(document)
            await unit_of_work.processing_runs.add(processing_run)
            await unit_of_work.commit()

        return RegisteredDocument(
            document_id=document.id,
            processing_run_id=processing_run.id,
            accepted_at=accepted_at,
        )
