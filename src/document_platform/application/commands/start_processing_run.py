"""Start the initial processing state for a durable processing run."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from document_platform.application.ports import Clock, UnitOfWorkFactory
from document_platform.domain.documents import DocumentStatus
from document_platform.domain.processing import ProcessingRunStatus


@dataclass(frozen=True, slots=True)
class StartProcessingRun:
    processing_run_id: UUID


@dataclass(frozen=True, slots=True)
class ProcessingRunStarted:
    processing_run_id: UUID
    started_at: datetime
    replayed: bool


class ProcessingRunNotFound(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"processing run not found: {processing_run_id}")


class ProcessingRunDocumentNotFound(RuntimeError):
    def __init__(self, document_id: UUID) -> None:
        super().__init__(f"processing run document not found: {document_id}")


class InvalidProcessingRunStart(RuntimeError):
    def __init__(self, processing_run_id: UUID, status: ProcessingRunStatus) -> None:
        super().__init__(f"processing run cannot start from {status}: {processing_run_id}")


class InvalidProcessingDocumentStart(RuntimeError):
    def __init__(self, document_id: UUID, status: DocumentStatus) -> None:
        super().__init__(f"document cannot enter processing from {status}: {document_id}")


class StartProcessingRunHandler:
    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def __call__(self, command: StartProcessingRun) -> ProcessingRunStarted:
        async with self._unit_of_work_factory() as unit_of_work:
            run = await unit_of_work.processing_runs.get(command.processing_run_id)
            if run is None:
                raise ProcessingRunNotFound(command.processing_run_id)
            if run.status is ProcessingRunStatus.RUNNING:
                if run.started_at is None:
                    raise RuntimeError("a running processing run must have a start time")
                return ProcessingRunStarted(run.id, run.started_at, replayed=True)
            if run.status is not ProcessingRunStatus.QUEUED:
                raise InvalidProcessingRunStart(run.id, run.status)

            document = await unit_of_work.documents.get(run.document_id)
            if document is None:
                raise ProcessingRunDocumentNotFound(run.document_id)
            if document.status is DocumentStatus.PROCESSING and run.previous_run_id is not None:
                started_at = self._clock()
                await unit_of_work.processing_runs.update(run.start(at=started_at))
                await unit_of_work.commit()
                return ProcessingRunStarted(run.id, started_at, replayed=False)
            if document.status is not DocumentStatus.UPLOADED:
                raise InvalidProcessingDocumentStart(document.id, document.status)

            started_at = self._clock()
            await unit_of_work.documents.update(document.start_processing(at=started_at))
            await unit_of_work.processing_runs.update(run.start(at=started_at))
            await unit_of_work.commit()
            return ProcessingRunStarted(run.id, started_at, replayed=False)
