"""Create a controlled, durable reprocessing operation."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from document_platform.application.ports import Clock, IdGenerator, UnitOfWorkFactory
from document_platform.domain.documents import Document, DocumentStatus
from document_platform.domain.processing import (
    ConflictingReprocessingIdempotencyKey,
    ProcessingRun,
    ProcessingRunStatus,
    ReprocessingOperation,
    WorkflowStartRequest,
)


@dataclass(frozen=True, slots=True)
class RequestDocumentReprocessing:
    document_id: UUID
    requested_by: str
    reason: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class DocumentReprocessingRequested:
    operation_id: UUID
    document_id: UUID
    source_run_id: UUID
    replacement_run_id: UUID
    requested_at: datetime
    replayed: bool


class ReprocessingDocumentNotFound(RuntimeError):
    def __init__(self, document_id: UUID) -> None:
        super().__init__(f"document not found for reprocessing: {document_id}")


class ReprocessingRunNotFound(RuntimeError):
    def __init__(self, document_id: UUID) -> None:
        super().__init__(f"processing run not found for reprocessing document: {document_id}")


class ReprocessingRunNotTerminal(RuntimeError):
    def __init__(self, processing_run_id: UUID, status: ProcessingRunStatus) -> None:
        super().__init__(f"processing run is not terminal: {processing_run_id} ({status})")


class InvalidReprocessingDocumentState(RuntimeError):
    def __init__(self, document_id: UUID, status: DocumentStatus) -> None:
        super().__init__(f"document cannot be reprocessed from {status}: {document_id}")


class RequestDocumentReprocessingHandler:
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

    async def __call__(
        self,
        command: RequestDocumentReprocessing,
    ) -> DocumentReprocessingRequested:
        async with self._unit_of_work_factory() as unit_of_work:
            document = await unit_of_work.documents.get_for_update(command.document_id)
            if document is None:
                raise ReprocessingDocumentNotFound(command.document_id)

            replay = await unit_of_work.reprocessing_operations.get(
                document_id=document.id,
                idempotency_key=command.idempotency_key,
            )
            if replay is not None:
                _ensure_replay_matches(command, replay)
                return _to_result(replay, replayed=True)

            source_run = await unit_of_work.processing_runs.get_latest_for_document(document.id)
            if source_run is None:
                raise ReprocessingRunNotFound(document.id)
            if source_run.status not in _TERMINAL_PROCESSING_RUN_STATUSES:
                raise ReprocessingRunNotTerminal(source_run.id, source_run.status)

            requested_at = self._clock()
            replacement_run = ProcessingRun.queue(
                run_id=self._id_generator(),
                document_id=document.id,
                previous_run_id=source_run.id,
                queued_at=requested_at,
            )
            operation = ReprocessingOperation.request(
                operation_id=self._id_generator(),
                document_id=document.id,
                source_run_id=source_run.id,
                replacement_run_id=replacement_run.id,
                requested_by=command.requested_by,
                reason=command.reason,
                idempotency_key=command.idempotency_key,
                requested_at=requested_at,
            )
            workflow_start_request = WorkflowStartRequest.request(
                processing_run_id=replacement_run.id,
                requested_at=requested_at,
            )

            updated_document = _prepare_document_for_reprocessing(document, requested_at)
            if updated_document != document:
                await unit_of_work.documents.update(updated_document)
            await unit_of_work.processing_runs.add(replacement_run)
            await unit_of_work.reprocessing_operations.add(operation)
            await unit_of_work.workflow_start_requests.add(workflow_start_request)
            await unit_of_work.commit()
            return _to_result(operation, replayed=False)


_TERMINAL_PROCESSING_RUN_STATUSES = frozenset(
    {
        ProcessingRunStatus.COMPLETED,
        ProcessingRunStatus.FAILED,
        ProcessingRunStatus.CANCELLED,
    }
)


def _ensure_replay_matches(
    command: RequestDocumentReprocessing,
    operation: ReprocessingOperation,
) -> None:
    if operation.requested_by != command.requested_by:
        raise ConflictingReprocessingIdempotencyKey(command.idempotency_key)
    operation.ensure_replay_matches(
        source_run_id=operation.source_run_id,
        reason=command.reason,
    )


def _prepare_document_for_reprocessing(document: Document, at: datetime) -> Document:
    if document.status in {
        DocumentStatus.APPROVED,
        DocumentStatus.REJECTED,
        DocumentStatus.FAILED,
    }:
        return document.reopen_for_reprocessing(at=at)
    if document.status is DocumentStatus.UPLOADED:
        return document.start_processing(at=at)
    if document.status is DocumentStatus.PROCESSING:
        return document
    raise InvalidReprocessingDocumentState(document.id, document.status)


def _to_result(
    operation: ReprocessingOperation,
    *,
    replayed: bool,
) -> DocumentReprocessingRequested:
    return DocumentReprocessingRequested(
        operation_id=operation.id,
        document_id=operation.document_id,
        source_run_id=operation.source_run_id,
        replacement_run_id=operation.replacement_run_id,
        requested_at=operation.requested_at,
        replayed=replayed,
    )
