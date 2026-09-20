"""Initial processing-run application tests."""

from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from document_platform.application.commands import (
    InvalidProcessingRunStart,
    ProcessingRunStarted,
    StartProcessingRun,
    StartProcessingRunHandler,
)
from document_platform.application.ports import UnitOfWork
from document_platform.domain.documents import Document
from document_platform.domain.processing import ProcessingRun

QUEUED_AT = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
STARTED_AT = QUEUED_AT + timedelta(seconds=2)
DOCUMENT_ID = UUID("41414141-4141-4141-8141-414141414141")
RUN_ID = UUID("42424242-4242-4242-8242-424242424242")


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


def document() -> Document:
    return Document.accept_pdf(
        document_id=DOCUMENT_ID,
        original_filename="supplier-invoice.pdf",
        size_bytes=42_000,
        page_count=2,
        content_sha256="a" * 64,
        storage_key="blobs/sha256/aa/" + "a" * 64,
        accepted_at=QUEUED_AT,
    )


def queued_run() -> ProcessingRun:
    return ProcessingRun.queue(run_id=RUN_ID, document_id=DOCUMENT_ID, queued_at=QUEUED_AT)


def handler(unit_of_work: RecordingUnitOfWork) -> StartProcessingRunHandler:
    return StartProcessingRunHandler(
        unit_of_work_factory=lambda: cast(UnitOfWork, unit_of_work),
        clock=lambda: STARTED_AT,
    )


@pytest.mark.anyio
async def test_starts_the_document_and_processing_run_atomically() -> None:
    unit_of_work = RecordingUnitOfWork(document(), queued_run())

    result = await handler(unit_of_work)(StartProcessingRun(RUN_ID))

    assert result == ProcessingRunStarted(RUN_ID, STARTED_AT, replayed=False)
    assert unit_of_work.documents.updated[0].status.value == "PROCESSING"
    assert unit_of_work.processing_runs.updated[0].status.value == "RUNNING"
    assert unit_of_work.processing_runs.updated[0].attempt_count == 1
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_replays_a_started_run_without_a_second_transition() -> None:
    unit_of_work = RecordingUnitOfWork(document(), queued_run())
    started = await handler(unit_of_work)(StartProcessingRun(RUN_ID))

    replay = await handler(unit_of_work)(StartProcessingRun(RUN_ID))

    assert started.replayed is False
    assert replay == ProcessingRunStarted(RUN_ID, STARTED_AT, replayed=True)
    assert len(unit_of_work.documents.updated) == 1
    assert len(unit_of_work.processing_runs.updated) == 1
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_rejects_starting_a_terminal_run() -> None:
    completed_run = queued_run().start(at=STARTED_AT).complete(at=STARTED_AT)
    unit_of_work = RecordingUnitOfWork(document(), completed_run)

    with pytest.raises(InvalidProcessingRunStart, match="COMPLETED"):
        await handler(unit_of_work)(StartProcessingRun(RUN_ID))

    assert unit_of_work.commit_count == 0


@pytest.mark.anyio
async def test_starts_a_reprocessing_run_without_restarting_the_document() -> None:
    processing_document = document().start_processing(at=STARTED_AT)
    reprocessing_run = ProcessingRun.queue(
        run_id=RUN_ID,
        document_id=DOCUMENT_ID,
        previous_run_id=UUID("43434343-4343-4434-8434-434343434343"),
        queued_at=QUEUED_AT,
    )
    unit_of_work = RecordingUnitOfWork(processing_document, reprocessing_run)

    result = await handler(unit_of_work)(StartProcessingRun(RUN_ID))

    assert result == ProcessingRunStarted(RUN_ID, STARTED_AT, replayed=False)
    assert unit_of_work.documents.updated == []
    assert unit_of_work.processing_runs.updated[0].status.value == "RUNNING"
    assert unit_of_work.commit_count == 1
