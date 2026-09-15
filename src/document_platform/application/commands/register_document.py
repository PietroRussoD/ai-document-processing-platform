"""Register an already validated and durably stored PDF."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from document_platform.application.ports import (
    Clock,
    IdGenerator,
    UnitOfWork,
    UnitOfWorkFactory,
    UploadIdempotencyRecordAlreadyExists,
)
from document_platform.application.upload_idempotency import (
    IdempotencyKey,
    UploadIdempotencyRecord,
    UploadRequestFingerprint,
)
from document_platform.domain.documents import PDF_MEDIA_TYPE, Document
from document_platform.domain.processing import ProcessingRun, WorkflowStartRequest


@dataclass(frozen=True, slots=True)
class RegisterDocument:
    idempotency_key: str
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
    replayed: bool


class InconsistentIdempotencyRecord(RuntimeError):
    def __init__(self, key: IdempotencyKey) -> None:
        super().__init__(f"idempotency record references a missing processing run: {key.value}")


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
        key = IdempotencyKey(command.idempotency_key)
        request_fingerprint = UploadRequestFingerprint.create(
            original_filename=command.original_filename,
            media_type=PDF_MEDIA_TYPE,
            content_sha256=command.content_sha256,
        )

        try:
            return await self._register_or_replay(command, key, request_fingerprint)
        except UploadIdempotencyRecordAlreadyExists:
            async with self._unit_of_work_factory() as unit_of_work:
                replay = await self._replay(unit_of_work, key, request_fingerprint)
                if replay is None:
                    raise InconsistentIdempotencyRecord(key) from None
                return replay

    async def _register_or_replay(
        self,
        command: RegisterDocument,
        key: IdempotencyKey,
        request_fingerprint: UploadRequestFingerprint,
    ) -> RegisteredDocument:
        async with self._unit_of_work_factory() as unit_of_work:
            replay = await self._replay(unit_of_work, key, request_fingerprint)
            if replay is not None:
                return replay

            return await self._register_new(unit_of_work, command, key, request_fingerprint)

    async def _register_new(
        self,
        unit_of_work: UnitOfWork,
        command: RegisterDocument,
        key: IdempotencyKey,
        request_fingerprint: UploadRequestFingerprint,
    ) -> RegisteredDocument:
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

        idempotency_record = UploadIdempotencyRecord(
            key=key,
            request_fingerprint=request_fingerprint,
            processing_run_id=processing_run.id,
            recorded_at=accepted_at,
        )
        workflow_start_request = WorkflowStartRequest.request(
            processing_run_id=processing_run.id,
            requested_at=accepted_at,
        )

        await unit_of_work.documents.add(document)
        await unit_of_work.processing_runs.add(processing_run)
        await unit_of_work.upload_idempotency.add(idempotency_record)
        await unit_of_work.workflow_start_requests.add(workflow_start_request)
        await unit_of_work.commit()

        return RegisteredDocument(
            document_id=document.id,
            processing_run_id=processing_run.id,
            accepted_at=accepted_at,
            replayed=False,
        )

    @staticmethod
    async def _replay(
        unit_of_work: UnitOfWork,
        key: IdempotencyKey,
        request_fingerprint: UploadRequestFingerprint,
    ) -> RegisteredDocument | None:
        record = await unit_of_work.upload_idempotency.get(key)
        if record is None:
            return None

        record.ensure_replay_matches(request_fingerprint)
        processing_run = await unit_of_work.processing_runs.get(record.processing_run_id)
        if processing_run is None:
            raise InconsistentIdempotencyRecord(key)

        return RegisteredDocument(
            document_id=processing_run.document_id,
            processing_run_id=processing_run.id,
            accepted_at=record.recorded_at,
            replayed=True,
        )
