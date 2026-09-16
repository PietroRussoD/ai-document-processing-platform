"""Processing-run completion application tests."""

from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from document_platform.application.commands import (
    CompleteProcessingRun,
    CompleteProcessingRunHandler,
    InvalidProcessingRunCompletion,
    ProcessingRunCompleted,
)
from document_platform.application.ports import UnitOfWork
from document_platform.domain.processing import ProcessingRun

QUEUED_AT = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
STARTED_AT = QUEUED_AT + timedelta(seconds=1)
COMPLETED_AT = QUEUED_AT + timedelta(seconds=2)
DOCUMENT_ID = UUID("b1b1b1b1-b1b1-41b1-81b1-b1b1b1b1b1b1")
RUN_ID = UUID("b2b2b2b2-b2b2-42b2-82b2-b2b2b2b2b2b2")


class RecordingProcessingRunRepository:
    def __init__(self, run: ProcessingRun) -> None:
        self.run = run
        self.updated: list[ProcessingRun] = []

    async def get(self, run_id: UUID) -> ProcessingRun | None:
        return self.run if run_id == self.run.id else None

    async def update(self, run: ProcessingRun) -> None:
        self.updated.append(run)
        self.run = run


class RecordingUnitOfWork:
    def __init__(self, run: ProcessingRun) -> None:
        self.processing_runs = RecordingProcessingRunRepository(run)
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


def running_run() -> ProcessingRun:
    return ProcessingRun.queue(
        run_id=RUN_ID,
        document_id=DOCUMENT_ID,
        queued_at=QUEUED_AT,
    ).start(at=STARTED_AT)


def handler(unit_of_work: RecordingUnitOfWork) -> CompleteProcessingRunHandler:
    return CompleteProcessingRunHandler(
        unit_of_work_factory=lambda: cast(UnitOfWork, unit_of_work),
        clock=lambda: COMPLETED_AT,
    )


@pytest.mark.anyio
async def test_completes_a_running_processing_run() -> None:
    unit_of_work = RecordingUnitOfWork(running_run())

    result = await handler(unit_of_work)(CompleteProcessingRun(RUN_ID))

    assert result == ProcessingRunCompleted(RUN_ID, COMPLETED_AT, replayed=False)
    assert unit_of_work.processing_runs.updated[0].status.value == "COMPLETED"
    assert unit_of_work.processing_runs.updated[0].finished_at == COMPLETED_AT
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_replays_a_completed_run_without_a_second_transition() -> None:
    unit_of_work = RecordingUnitOfWork(running_run())
    command = CompleteProcessingRun(RUN_ID)

    await handler(unit_of_work)(command)
    replay = await handler(unit_of_work)(command)

    assert replay == ProcessingRunCompleted(RUN_ID, COMPLETED_AT, replayed=True)
    assert len(unit_of_work.processing_runs.updated) == 1
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_rejects_completion_before_a_run_has_started() -> None:
    queued = ProcessingRun.queue(run_id=RUN_ID, document_id=DOCUMENT_ID, queued_at=QUEUED_AT)
    unit_of_work = RecordingUnitOfWork(queued)

    with pytest.raises(InvalidProcessingRunCompletion, match="QUEUED"):
        await handler(unit_of_work)(CompleteProcessingRun(RUN_ID))

    assert unit_of_work.commit_count == 0
