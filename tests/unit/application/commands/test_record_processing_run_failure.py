"""Terminal processing-failure application tests."""

from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from document_platform.application.commands import (
    ConflictingProcessingRunFailure,
    ProcessingRunFailureRecorded,
    RecordProcessingRunFailure,
    RecordProcessingRunFailureHandler,
)
from document_platform.application.ports import UnitOfWork
from document_platform.domain.documents import Document
from document_platform.domain.processing import (
    ProcessingFailure,
    ProcessingFailureCode,
    ProcessingRun,
    ProcessingStage,
)

QUEUED_AT = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)
FAILED_AT = QUEUED_AT + timedelta(seconds=2)
DOCUMENT_ID = UUID("c1c1c1c1-c1c1-41c1-81c1-c1c1c1c1c1c1")
RUN_ID = UUID("c2c2c2c2-c2c2-42c2-82c2-c2c2c2c2c2c2")
FAILURE = ProcessingFailure(
    stage=ProcessingStage.EMBEDDED_TEXT_EXTRACTION,
    code=ProcessingFailureCode.ACTIVITY_RETRY_EXHAUSTED,
)


class RecordingDocumentRepository:
    def __init__(self, document: Document) -> None:
        self.document = document
        self.updated: list[Document] = []

    async def get(self, document_id: UUID) -> Document | None:
        return self.document if document_id == self.document.id else None

    async def update(self, document: Document) -> None:
        self.updated.append(document)
        self.document = document


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
    def __init__(self, document: Document, run: ProcessingRun) -> None:
        self.documents = RecordingDocumentRepository(document)
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


def processing_document() -> Document:
    return Document.accept_pdf(
        document_id=DOCUMENT_ID,
        original_filename="supplier-invoice.pdf",
        size_bytes=42_000,
        page_count=2,
        content_sha256="c" * 64,
        storage_key="blobs/sha256/cc/" + "c" * 64,
        accepted_at=QUEUED_AT,
    ).start_processing(at=QUEUED_AT + timedelta(seconds=1))


def running_run() -> ProcessingRun:
    return ProcessingRun.queue(
        run_id=RUN_ID,
        document_id=DOCUMENT_ID,
        queued_at=QUEUED_AT,
    ).start(at=QUEUED_AT + timedelta(seconds=1))


def handler(unit_of_work: RecordingUnitOfWork) -> RecordProcessingRunFailureHandler:
    return RecordProcessingRunFailureHandler(
        unit_of_work_factory=lambda: cast(UnitOfWork, unit_of_work),
        clock=lambda: FAILED_AT,
    )


@pytest.mark.anyio
async def test_fails_the_run_and_document_atomically() -> None:
    unit_of_work = RecordingUnitOfWork(processing_document(), running_run())

    result = await handler(unit_of_work)(RecordProcessingRunFailure(RUN_ID, FAILURE))

    assert result == ProcessingRunFailureRecorded(RUN_ID, FAILED_AT, replayed=False)
    assert unit_of_work.processing_runs.updated[0].status.value == "FAILED"
    assert unit_of_work.processing_runs.updated[0].failure == FAILURE
    assert unit_of_work.documents.updated[0].status.value == "FAILED"
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_replays_the_same_failure_without_a_second_write() -> None:
    unit_of_work = RecordingUnitOfWork(processing_document(), running_run())
    command = RecordProcessingRunFailure(RUN_ID, FAILURE)

    await handler(unit_of_work)(command)
    replay = await handler(unit_of_work)(command)

    assert replay == ProcessingRunFailureRecorded(RUN_ID, FAILED_AT, replayed=True)
    assert len(unit_of_work.processing_runs.updated) == 1
    assert len(unit_of_work.documents.updated) == 1
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_rejects_conflicting_failure_replay() -> None:
    unit_of_work = RecordingUnitOfWork(processing_document(), running_run())
    await handler(unit_of_work)(RecordProcessingRunFailure(RUN_ID, FAILURE))

    with pytest.raises(ConflictingProcessingRunFailure):
        await handler(unit_of_work)(
            RecordProcessingRunFailure(
                RUN_ID,
                ProcessingFailure(
                    stage=ProcessingStage.OCR_TEXT_EXTRACTION,
                    code=ProcessingFailureCode.ACTIVITY_RETRY_EXHAUSTED,
                ),
            )
        )

    assert unit_of_work.commit_count == 1
