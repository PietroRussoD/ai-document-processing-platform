"""Controlled document-reprocessing application tests."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from document_platform.application.commands import (
    DocumentReprocessingRequested,
    ReprocessingRunNotTerminal,
    RequestDocumentReprocessing,
    RequestDocumentReprocessingHandler,
)
from document_platform.application.ports import UnitOfWork
from document_platform.domain.documents import Document, DocumentStatus
from document_platform.domain.processing import (
    ConflictingReprocessingIdempotencyKey,
    ProcessingRun,
    ReprocessingOperation,
    WorkflowStartRequest,
)

DOCUMENT_ID = UUID("11111111-aaaa-4111-8111-111111111111")
SOURCE_RUN_ID = UUID("22222222-bbbb-4222-8222-222222222222")
REPLACEMENT_RUN_ID = UUID("33333333-cccc-4333-8333-333333333333")
OPERATION_ID = UUID("44444444-dddd-4444-8444-444444444444")
ACCEPTED_AT = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)
REQUESTED_AT = ACCEPTED_AT + timedelta(minutes=5)


class RecordingDocumentRepository:
    def __init__(self, document: Document) -> None:
        self.document = document
        self.updated: list[Document] = []

    async def get_for_update(self, document_id: UUID) -> Document | None:
        return self.document if document_id == self.document.id else None

    async def update(self, document: Document) -> None:
        self.updated.append(document)
        self.document = document


class RecordingProcessingRunRepository:
    def __init__(self, source_run: ProcessingRun) -> None:
        self.runs = {source_run.id: source_run}
        self.added: list[ProcessingRun] = []

    async def get_latest_for_document(self, document_id: UUID) -> ProcessingRun | None:
        matching = [run for run in self.runs.values() if run.document_id == document_id]
        return max(matching, key=lambda run: (run.queued_at, str(run.id)), default=None)

    async def add(self, run: ProcessingRun) -> None:
        self.runs[run.id] = run
        self.added.append(run)


class RecordingReprocessingOperationRepository:
    def __init__(self) -> None:
        self.operations: dict[tuple[UUID, str], ReprocessingOperation] = {}
        self.added: list[ReprocessingOperation] = []

    async def add(self, operation: ReprocessingOperation) -> None:
        self.operations[(operation.document_id, operation.idempotency_key)] = operation
        self.added.append(operation)

    async def get(
        self,
        *,
        document_id: UUID,
        idempotency_key: str,
    ) -> ReprocessingOperation | None:
        return self.operations.get((document_id, idempotency_key))


class RecordingWorkflowStartRequestRepository:
    def __init__(self) -> None:
        self.added: list[WorkflowStartRequest] = []

    async def add(self, request: WorkflowStartRequest) -> None:
        self.added.append(request)


class RecordingUnitOfWork:
    def __init__(self, document: Document, source_run: ProcessingRun) -> None:
        self.documents = RecordingDocumentRepository(document)
        self.processing_runs = RecordingProcessingRunRepository(source_run)
        self.reprocessing_operations = RecordingReprocessingOperationRepository()
        self.workflow_start_requests = RecordingWorkflowStartRequestRepository()
        self.commit_count = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.commit_count += 1


def document() -> Document:
    return Document.accept_pdf(
        document_id=DOCUMENT_ID,
        original_filename="supplier-invoice.pdf",
        size_bytes=42_000,
        page_count=2,
        content_sha256="a" * 64,
        storage_key="blobs/sha256/aa/" + "a" * 64,
        accepted_at=ACCEPTED_AT,
    )


def completed_source_run() -> ProcessingRun:
    return (
        ProcessingRun.queue(
            run_id=SOURCE_RUN_ID,
            document_id=DOCUMENT_ID,
            queued_at=ACCEPTED_AT,
        )
        .start(at=ACCEPTED_AT + timedelta(seconds=1))
        .complete(at=ACCEPTED_AT + timedelta(seconds=2))
    )


def failed_source_run() -> ProcessingRun:
    return (
        ProcessingRun.queue(
            run_id=SOURCE_RUN_ID,
            document_id=DOCUMENT_ID,
            queued_at=ACCEPTED_AT,
        )
        .start(at=ACCEPTED_AT + timedelta(seconds=1))
        .fail(at=ACCEPTED_AT + timedelta(seconds=2))
    )


def command(**overrides: object) -> RequestDocumentReprocessing:
    values: dict[str, object] = {
        "document_id": DOCUMENT_ID,
        "requested_by": "local-review-operator",
        "reason": "Retry after the upstream outage was resolved.",
        "idempotency_key": "reprocess-001",
    }
    values.update(overrides)
    return RequestDocumentReprocessing(**values)  # type: ignore[arg-type]


def handler(
    unit_of_work: RecordingUnitOfWork,
    ids: Iterator[UUID] | None = None,
) -> RequestDocumentReprocessingHandler:
    generated_ids = ids or iter((REPLACEMENT_RUN_ID, OPERATION_ID))
    return RequestDocumentReprocessingHandler(
        unit_of_work_factory=lambda: cast(UnitOfWork, unit_of_work),
        clock=lambda: REQUESTED_AT,
        id_generator=lambda: next(generated_ids),
    )


@pytest.mark.anyio
async def test_creates_a_replacement_run_audit_and_workflow_request_atomically() -> None:
    resolved_document = (
        document()
        .start_processing(at=ACCEPTED_AT + timedelta(seconds=1))
        .approve(at=ACCEPTED_AT + timedelta(seconds=2))
    )
    unit_of_work = RecordingUnitOfWork(resolved_document, completed_source_run())

    result = await handler(unit_of_work)(command())

    assert result == DocumentReprocessingRequested(
        operation_id=OPERATION_ID,
        document_id=DOCUMENT_ID,
        source_run_id=SOURCE_RUN_ID,
        replacement_run_id=REPLACEMENT_RUN_ID,
        requested_at=REQUESTED_AT,
        replayed=False,
    )
    assert unit_of_work.documents.document.status is DocumentStatus.PROCESSING
    assert unit_of_work.documents.document.version == 3
    assert unit_of_work.processing_runs.added[0].previous_run_id == SOURCE_RUN_ID
    assert unit_of_work.reprocessing_operations.added[0].replacement_run_id == REPLACEMENT_RUN_ID
    assert unit_of_work.workflow_start_requests.added[0].processing_run_id == REPLACEMENT_RUN_ID
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_reprocessing_a_failed_run_keeps_an_already_processing_document() -> None:
    processing_document = document().start_processing(at=ACCEPTED_AT + timedelta(seconds=1))
    unit_of_work = RecordingUnitOfWork(processing_document, failed_source_run())

    result = await handler(unit_of_work)(command())

    assert result.replayed is False
    assert unit_of_work.documents.updated == []
    assert unit_of_work.documents.document.status is DocumentStatus.PROCESSING
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_replays_an_equivalent_reprocessing_request_without_a_second_write() -> None:
    resolved_document = (
        document()
        .start_processing(at=ACCEPTED_AT + timedelta(seconds=1))
        .approve(at=ACCEPTED_AT + timedelta(seconds=2))
    )
    unit_of_work = RecordingUnitOfWork(resolved_document, completed_source_run())
    existing = ReprocessingOperation.request(
        operation_id=OPERATION_ID,
        document_id=DOCUMENT_ID,
        source_run_id=SOURCE_RUN_ID,
        replacement_run_id=REPLACEMENT_RUN_ID,
        requested_by="local-review-operator",
        reason="Retry after the upstream outage was resolved.",
        idempotency_key="reprocess-001",
        requested_at=REQUESTED_AT,
    )
    await unit_of_work.reprocessing_operations.add(existing)

    result = await handler(unit_of_work)(command())

    assert result.replayed is True
    assert unit_of_work.processing_runs.added == []
    assert unit_of_work.workflow_start_requests.added == []
    assert unit_of_work.commit_count == 0


@pytest.mark.anyio
async def test_rejects_a_conflicting_idempotent_reprocessing_request() -> None:
    resolved_document = (
        document()
        .start_processing(at=ACCEPTED_AT + timedelta(seconds=1))
        .approve(at=ACCEPTED_AT + timedelta(seconds=2))
    )
    unit_of_work = RecordingUnitOfWork(resolved_document, completed_source_run())
    existing = ReprocessingOperation.request(
        operation_id=OPERATION_ID,
        document_id=DOCUMENT_ID,
        source_run_id=SOURCE_RUN_ID,
        replacement_run_id=REPLACEMENT_RUN_ID,
        requested_by="local-review-operator",
        reason="Retry after the upstream outage was resolved.",
        idempotency_key="reprocess-001",
        requested_at=REQUESTED_AT,
    )
    await unit_of_work.reprocessing_operations.add(existing)

    with pytest.raises(ConflictingReprocessingIdempotencyKey):
        await handler(unit_of_work)(command(reason="Retry after a different outage."))

    assert unit_of_work.commit_count == 0


@pytest.mark.anyio
async def test_rejects_reprocessing_an_active_run() -> None:
    unit_of_work = RecordingUnitOfWork(
        document(),
        ProcessingRun.queue(
            run_id=SOURCE_RUN_ID,
            document_id=DOCUMENT_ID,
            queued_at=ACCEPTED_AT,
        ),
    )

    with pytest.raises(ReprocessingRunNotTerminal):
        await handler(unit_of_work)(command())

    assert unit_of_work.commit_count == 0
