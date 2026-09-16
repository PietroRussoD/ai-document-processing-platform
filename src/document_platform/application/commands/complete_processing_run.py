"""Complete a processing run after its current workflow stages succeed."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from document_platform.application.ports import Clock, UnitOfWorkFactory
from document_platform.domain.processing import ProcessingRunStatus


@dataclass(frozen=True, slots=True)
class CompleteProcessingRun:
    processing_run_id: UUID


@dataclass(frozen=True, slots=True)
class ProcessingRunCompleted:
    processing_run_id: UUID
    completed_at: datetime
    replayed: bool


class ProcessingRunCompletionNotFound(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"processing run not found: {processing_run_id}")


class InvalidProcessingRunCompletion(RuntimeError):
    def __init__(self, processing_run_id: UUID, status: ProcessingRunStatus) -> None:
        super().__init__(f"processing run cannot complete from {status}: {processing_run_id}")


class CompleteProcessingRunHandler:
    def __init__(self, *, unit_of_work_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def __call__(self, command: CompleteProcessingRun) -> ProcessingRunCompleted:
        async with self._unit_of_work_factory() as unit_of_work:
            run = await unit_of_work.processing_runs.get(command.processing_run_id)
            if run is None:
                raise ProcessingRunCompletionNotFound(command.processing_run_id)
            if run.status is ProcessingRunStatus.COMPLETED:
                if run.finished_at is None:
                    raise RuntimeError("a completed processing run must have a finish time")
                return ProcessingRunCompleted(run.id, run.finished_at, replayed=True)
            if run.status is not ProcessingRunStatus.RUNNING:
                raise InvalidProcessingRunCompletion(run.id, run.status)

            completed_at = self._clock()
            await unit_of_work.processing_runs.update(run.complete(at=completed_at))
            await unit_of_work.commit()
            return ProcessingRunCompleted(run.id, completed_at, replayed=False)
