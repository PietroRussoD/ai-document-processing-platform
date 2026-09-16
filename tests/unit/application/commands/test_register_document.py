"""Register-document application tests."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self
from uuid import UUID

import pytest

from document_platform.application.commands import (
    InconsistentIdempotencyRecord,
    RegisterDocument,
    RegisterDocumentHandler,
)
from document_platform.application.ports import (
    DocumentClassificationRepository,
    DocumentOcrExtractionRepository,
    DocumentRepository,
    DocumentTextExtractionRepository,
    DocumentTextSelectionRepository,
    InvoiceExtractionRepository,
    ProcessingRunRepository,
    UploadIdempotencyRecordAlreadyExists,
    UploadIdempotencyRepository,
    WorkflowStartRequestRepository,
)
from document_platform.application.upload_idempotency import (
    ConflictingIdempotencyKey,
    IdempotencyKey,
    UploadIdempotencyRecord,
    UploadRequestFingerprint,
)
from document_platform.domain.documents import Document, InvalidDocument
from document_platform.domain.processing import ProcessingRun, WorkflowStartRequest

DOCUMENT_ID = UUID("c1e87668-329b-4862-87fc-e4f5150e233c")
RUN_ID = UUID("91c5567b-8951-4713-b9c6-211055d4bb3e")
ACCEPTED_AT = datetime(2026, 9, 13, 15, 0, tzinfo=UTC)


class RecordingDocumentRepository:
    def __init__(self) -> None:
        self.added: list[Document] = []

    async def add(self, document: Document) -> None:
        self.added.append(document)

    async def get(self, document_id: UUID) -> Document | None:
        return next((document for document in self.added if document.id == document_id), None)

    async def update(self, document: Document) -> None:
        raise NotImplementedError


class RecordingProcessingRunRepository:
    def __init__(self, *, fail_on_add: bool = False) -> None:
        self.added: list[ProcessingRun] = []
        self.fail_on_add = fail_on_add

    async def add(self, run: ProcessingRun) -> None:
        if self.fail_on_add:
            raise SimulatedPersistenceFailure
        self.added.append(run)

    async def get(self, run_id: UUID) -> ProcessingRun | None:
        return next((run for run in self.added if run.id == run_id), None)

    async def update(self, run: ProcessingRun) -> None:
        raise NotImplementedError

    def seed(self, run: ProcessingRun) -> None:
        self.added.append(run)


class SimulatedPersistenceFailure(RuntimeError):
    pass


class RecordingUploadIdempotencyRepository:
    def __init__(self, *, fail_on_add: bool = False) -> None:
        self.records: dict[IdempotencyKey, UploadIdempotencyRecord] = {}
        self.fail_on_add = fail_on_add

    async def add(self, record: UploadIdempotencyRecord) -> None:
        if self.fail_on_add:
            raise UploadIdempotencyRecordAlreadyExists(record.key)
        self.records[record.key] = record

    async def get(self, key: IdempotencyKey) -> UploadIdempotencyRecord | None:
        return self.records.get(key)

    def seed(self, record: UploadIdempotencyRecord) -> None:
        self.records[record.key] = record


class RecordingWorkflowStartRequestRepository:
    def __init__(self) -> None:
        self.requests: dict[UUID, WorkflowStartRequest] = {}

    async def add(self, request: WorkflowStartRequest) -> None:
        self.requests[request.processing_run_id] = request

    async def get(self, processing_run_id: UUID) -> WorkflowStartRequest | None:
        return self.requests.get(processing_run_id)

    async def claim_pending(
        self,
        *,
        owner: str,
        claimed_at: datetime,
        lease_duration: timedelta,
        limit: int,
        token_generator: Callable[[], UUID],
    ) -> tuple[WorkflowStartRequest, ...]:
        raise NotImplementedError

    async def update(self, request: WorkflowStartRequest) -> None:
        self.requests[request.processing_run_id] = request


class UnusedDocumentTextExtractionRepository:
    async def add(self, extraction: object) -> None:
        raise AssertionError("not used")

    async def get(self, processing_run_id: UUID) -> None:
        raise AssertionError("not used")


class UnusedDocumentOcrExtractionRepository:
    async def add(self, extraction: object) -> None:
        raise AssertionError("not used")

    async def get(self, processing_run_id: UUID) -> None:
        raise AssertionError("not used")


class UnusedDocumentTextSelectionRepository:
    async def add(self, selection: object) -> None:
        raise AssertionError("not used")

    async def get(self, processing_run_id: UUID) -> None:
        raise AssertionError("not used")


class UnusedDocumentClassificationRepository:
    async def add(self, classification: object) -> None:
        raise AssertionError("not used")

    async def get(self, processing_run_id: UUID) -> None:
        raise AssertionError("not used")


class UnusedInvoiceExtractionRepository:
    async def add(self, extraction: object) -> None:
        raise AssertionError("not used")

    async def get(self, processing_run_id: UUID) -> None:
        raise AssertionError("not used")


class RecordingUnitOfWork:
    def __init__(
        self,
        *,
        fail_on_run_add: bool = False,
        fail_on_idempotency_add: bool = False,
    ) -> None:
        self._documents = RecordingDocumentRepository()
        self._processing_runs = RecordingProcessingRunRepository(fail_on_add=fail_on_run_add)
        self._upload_idempotency = RecordingUploadIdempotencyRepository(
            fail_on_add=fail_on_idempotency_add
        )
        self._workflow_start_requests = RecordingWorkflowStartRequestRepository()
        self._document_text_extractions = UnusedDocumentTextExtractionRepository()
        self._document_ocr_extractions = UnusedDocumentOcrExtractionRepository()
        self._document_text_selections = UnusedDocumentTextSelectionRepository()
        self._document_classifications = UnusedDocumentClassificationRepository()
        self._invoice_extractions = UnusedInvoiceExtractionRepository()
        self.commit_count = 0
        self.exit_exception: type[BaseException] | None = None

    @property
    def documents(self) -> DocumentRepository:
        return self._documents

    @property
    def document_text_extractions(self) -> DocumentTextExtractionRepository:
        return self._document_text_extractions  # type: ignore[return-value]

    @property
    def document_ocr_extractions(self) -> DocumentOcrExtractionRepository:
        return self._document_ocr_extractions  # type: ignore[return-value]

    @property
    def document_text_selections(self) -> DocumentTextSelectionRepository:
        return self._document_text_selections  # type: ignore[return-value]

    @property
    def document_classifications(self) -> DocumentClassificationRepository:
        return self._document_classifications  # type: ignore[return-value]

    @property
    def invoice_extractions(self) -> InvoiceExtractionRepository:
        return self._invoice_extractions  # type: ignore[return-value]

    @property
    def processing_runs(self) -> ProcessingRunRepository:
        return self._processing_runs

    @property
    def upload_idempotency(self) -> UploadIdempotencyRepository:
        return self._upload_idempotency

    @property
    def workflow_start_requests(self) -> WorkflowStartRequestRepository:
        return self._workflow_start_requests

    @property
    def recorded_documents(self) -> tuple[Document, ...]:
        return tuple(self._documents.added)

    @property
    def recorded_processing_runs(self) -> tuple[ProcessingRun, ...]:
        return tuple(self._processing_runs.added)

    @property
    def recorded_idempotency_records(self) -> tuple[UploadIdempotencyRecord, ...]:
        return tuple(self._upload_idempotency.records.values())

    @property
    def recorded_workflow_start_requests(self) -> tuple[WorkflowStartRequest, ...]:
        return tuple(self._workflow_start_requests.requests.values())

    def seed_replay(
        self,
        processing_run: ProcessingRun,
        idempotency_record: UploadIdempotencyRecord,
    ) -> None:
        self._processing_runs.seed(processing_run)
        self._upload_idempotency.seed(idempotency_record)

    def seed_idempotency(self, idempotency_record: UploadIdempotencyRecord) -> None:
        self._upload_idempotency.seed(idempotency_record)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.exit_exception = exc_type

    async def commit(self) -> None:
        self.commit_count += 1

    async def rollback(self) -> None:
        pass


class SequenceIdGenerator:
    def __init__(self, *values: UUID) -> None:
        self._values = iter(values)

    def __call__(self) -> UUID:
        return next(self._values)


def command(**overrides: object) -> RegisterDocument:
    values: dict[str, object] = {
        "idempotency_key": "request-42",
        "original_filename": "supplier-invoice.pdf",
        "size_bytes": 42_000,
        "page_count": 2,
        "content_sha256": "c" * 64,
        "storage_key": "blobs/sha256/cc/" + "c" * 64,
    }
    values.update(overrides)
    return RegisterDocument(**values)  # type: ignore[arg-type]


def handler(unit_of_work: RecordingUnitOfWork) -> RegisterDocumentHandler:
    return RegisterDocumentHandler(
        unit_of_work_factory=lambda: unit_of_work,
        clock=lambda: ACCEPTED_AT,
        id_generator=SequenceIdGenerator(DOCUMENT_ID, RUN_ID),
    )


@pytest.mark.anyio
async def test_registers_a_document_and_initial_run_atomically() -> None:
    unit_of_work = RecordingUnitOfWork()

    result = await handler(unit_of_work)(command())

    assert result.document_id == DOCUMENT_ID
    assert result.processing_run_id == RUN_ID
    assert result.accepted_at == ACCEPTED_AT
    assert result.replayed is False
    assert unit_of_work.commit_count == 1
    assert unit_of_work.exit_exception is None

    document = unit_of_work.recorded_documents[0]
    processing_run = unit_of_work.recorded_processing_runs[0]
    assert document.id == DOCUMENT_ID
    assert document.accepted_at == ACCEPTED_AT
    assert processing_run.id == RUN_ID
    assert processing_run.document_id == DOCUMENT_ID
    assert processing_run.queued_at == ACCEPTED_AT
    idempotency_record = unit_of_work.recorded_idempotency_records[0]
    assert idempotency_record.processing_run_id == RUN_ID
    assert idempotency_record.recorded_at == ACCEPTED_AT
    workflow_start_request = unit_of_work.recorded_workflow_start_requests[0]
    assert workflow_start_request.processing_run_id == RUN_ID
    assert workflow_start_request.workflow_id == f"process-business-document/{RUN_ID}"
    assert workflow_start_request.requested_at == ACCEPTED_AT


@pytest.mark.anyio
async def test_does_not_write_or_commit_invalid_document_data() -> None:
    unit_of_work = RecordingUnitOfWork()
    entered = False

    def unit_of_work_factory() -> RecordingUnitOfWork:
        nonlocal entered
        entered = True
        return unit_of_work

    register = RegisterDocumentHandler(
        unit_of_work_factory=unit_of_work_factory,
        clock=lambda: ACCEPTED_AT,
        id_generator=SequenceIdGenerator(DOCUMENT_ID, RUN_ID),
    )

    with pytest.raises(InvalidDocument):
        await register(command(size_bytes=0))

    assert entered is True
    assert unit_of_work.recorded_documents == ()
    assert unit_of_work.recorded_processing_runs == ()
    assert unit_of_work.recorded_idempotency_records == ()
    assert unit_of_work.recorded_workflow_start_requests == ()
    assert unit_of_work.commit_count == 0


@pytest.mark.anyio
async def test_does_not_commit_when_a_repository_write_fails() -> None:
    unit_of_work = RecordingUnitOfWork(fail_on_run_add=True)

    with pytest.raises(SimulatedPersistenceFailure):
        await handler(unit_of_work)(command())

    assert unit_of_work.commit_count == 0
    assert unit_of_work.exit_exception is SimulatedPersistenceFailure


@pytest.mark.anyio
async def test_replays_the_original_acceptance_for_the_same_request() -> None:
    unit_of_work = RecordingUnitOfWork()
    processing_run = ProcessingRun.queue(
        run_id=RUN_ID,
        document_id=DOCUMENT_ID,
        queued_at=ACCEPTED_AT,
    )
    idempotency_record = UploadIdempotencyRecord(
        key=IdempotencyKey("request-42"),
        request_fingerprint=UploadRequestFingerprint.create(
            original_filename="supplier-invoice.pdf",
            media_type="application/pdf",
            content_sha256="c" * 64,
        ),
        processing_run_id=RUN_ID,
        recorded_at=ACCEPTED_AT,
    )
    unit_of_work.seed_replay(processing_run, idempotency_record)

    result = await handler(unit_of_work)(command())

    assert result.document_id == DOCUMENT_ID
    assert result.processing_run_id == RUN_ID
    assert result.replayed is True
    assert unit_of_work.commit_count == 0
    assert unit_of_work.recorded_documents == ()
    assert unit_of_work.recorded_workflow_start_requests == ()


@pytest.mark.anyio
async def test_rejects_reusing_a_key_for_different_content() -> None:
    unit_of_work = RecordingUnitOfWork()
    idempotency_record = UploadIdempotencyRecord(
        key=IdempotencyKey("request-42"),
        request_fingerprint=UploadRequestFingerprint.create(
            original_filename="supplier-invoice.pdf",
            media_type="application/pdf",
            content_sha256="a" * 64,
        ),
        processing_run_id=RUN_ID,
        recorded_at=ACCEPTED_AT,
    )
    unit_of_work.seed_idempotency(idempotency_record)

    with pytest.raises(ConflictingIdempotencyKey):
        await handler(unit_of_work)(command())

    assert unit_of_work.commit_count == 0


@pytest.mark.anyio
async def test_recovers_a_concurrent_same_request_registration() -> None:
    losing_unit_of_work = RecordingUnitOfWork(fail_on_idempotency_add=True)
    winning_unit_of_work = RecordingUnitOfWork()
    winning_run = ProcessingRun.queue(
        run_id=RUN_ID,
        document_id=DOCUMENT_ID,
        queued_at=ACCEPTED_AT,
    )
    winning_record = UploadIdempotencyRecord(
        key=IdempotencyKey("request-42"),
        request_fingerprint=UploadRequestFingerprint.create(
            original_filename="supplier-invoice.pdf",
            media_type="application/pdf",
            content_sha256="c" * 64,
        ),
        processing_run_id=RUN_ID,
        recorded_at=ACCEPTED_AT,
    )
    winning_unit_of_work.seed_replay(winning_run, winning_record)
    units_of_work = iter((losing_unit_of_work, winning_unit_of_work))
    register = RegisterDocumentHandler(
        unit_of_work_factory=lambda: next(units_of_work),
        clock=lambda: ACCEPTED_AT,
        id_generator=SequenceIdGenerator(DOCUMENT_ID, RUN_ID),
    )

    result = await register(command())

    assert result.document_id == DOCUMENT_ID
    assert result.processing_run_id == RUN_ID
    assert result.replayed is True
    assert losing_unit_of_work.commit_count == 0
    assert losing_unit_of_work.exit_exception is UploadIdempotencyRecordAlreadyExists


@pytest.mark.anyio
async def test_rejects_an_idempotency_record_with_a_missing_run() -> None:
    unit_of_work = RecordingUnitOfWork()
    unit_of_work.seed_idempotency(
        UploadIdempotencyRecord(
            key=IdempotencyKey("request-42"),
            request_fingerprint=UploadRequestFingerprint.create(
                original_filename="supplier-invoice.pdf",
                media_type="application/pdf",
                content_sha256="c" * 64,
            ),
            processing_run_id=RUN_ID,
            recorded_at=ACCEPTED_AT,
        )
    )

    with pytest.raises(InconsistentIdempotencyRecord):
        await handler(unit_of_work)(command())
