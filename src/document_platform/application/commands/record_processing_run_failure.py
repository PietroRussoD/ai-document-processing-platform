"""Persist a terminal processing failure and its document state atomically."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from document_platform.application.ports import Clock, UnitOfWorkFactory
from document_platform.domain.documents import DocumentStatus
from document_platform.domain.processing import (
    ProcessingFailure,
    ProcessingRunStatus,
)


@dataclass(frozen=True, slots=True)
class RecordProcessingRunFailure:
    processing_run_id: UUID
    failure: ProcessingFailure


@dataclass(frozen=True, slots=True)
class ProcessingRunFailureRecorded:
    processing_run_id: UUID
    failed_at: datetime
    replayed: bool


class ProcessingRunFailureNotFound(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"processing run not found: {processing_run_id}")


class ProcessingRunFailureDocumentNotFound(RuntimeError):
    def __init__(self, document_id: UUID) -> None:
        super().__init__(f"processing run document not found: {document_id}")


class InvalidProcessingRunFailure(RuntimeError):
    def __init__(self, processing_run_id: UUID, status: ProcessingRunStatus) -> None:
        super().__init__(f"processing run cannot fail from {status}: {processing_run_id}")


class ConflictingProcessingRunFailure(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(
            f"processing run failure conflicts with recorded evidence: {processing_run_id}"
        )


class InvalidProcessingFailureDocument(RuntimeError):
    def __init__(self, document_id: UUID, status: DocumentStatus) -> None:
        super().__init__(f"document cannot fail from {status}: {document_id}")


class RecordProcessingRunFailureHandler:
    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def __call__(self, command: RecordProcessingRunFailure) -> ProcessingRunFailureRecorded:
        async with self._unit_of_work_factory() as unit_of_work:
            run = await unit_of_work.processing_runs.get(command.processing_run_id)
            if run is None:
                raise ProcessingRunFailureNotFound(command.processing_run_id)
            if run.status is ProcessingRunStatus.FAILED:
                if run.failure != command.failure or run.finished_at is None:
                    raise ConflictingProcessingRunFailure(run.id)
                return ProcessingRunFailureRecorded(run.id, run.finished_at, replayed=True)
            if run.status not in {ProcessingRunStatus.RUNNING, ProcessingRunStatus.WAITING_RETRY}:
                raise InvalidProcessingRunFailure(run.id, run.status)

            document = await unit_of_work.documents.get(run.document_id)
            if document is None:
                raise ProcessingRunFailureDocumentNotFound(run.document_id)
            if document.status is not DocumentStatus.PROCESSING:
                raise InvalidProcessingFailureDocument(document.id, document.status)

            failed_at = self._clock()
            await unit_of_work.processing_runs.update(
                run.fail(at=failed_at, failure=command.failure)
            )
            await unit_of_work.documents.update(document.fail(at=failed_at))
            await unit_of_work.commit()
            return ProcessingRunFailureRecorded(run.id, failed_at, replayed=False)
