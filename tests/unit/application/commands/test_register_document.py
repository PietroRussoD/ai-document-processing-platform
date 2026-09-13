"""Register-document application tests."""

from datetime import UTC, datetime
from types import TracebackType
from typing import Self
from uuid import UUID

import pytest

from document_platform.application.commands import (
    RegisterDocument,
    RegisterDocumentHandler,
)
from document_platform.application.ports import (
    DocumentRepository,
    ProcessingRunRepository,
)
from document_platform.domain.documents import Document, InvalidDocument
from document_platform.domain.processing import ProcessingRun

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


class SimulatedPersistenceFailure(RuntimeError):
    pass


class RecordingUnitOfWork:
    def __init__(self, *, fail_on_run_add: bool = False) -> None:
        self._documents = RecordingDocumentRepository()
        self._processing_runs = RecordingProcessingRunRepository(fail_on_add=fail_on_run_add)
        self.commit_count = 0
        self.exit_exception: type[BaseException] | None = None

    @property
    def documents(self) -> DocumentRepository:
        return self._documents

    @property
    def processing_runs(self) -> ProcessingRunRepository:
        return self._processing_runs

    @property
    def recorded_documents(self) -> tuple[Document, ...]:
        return tuple(self._documents.added)

    @property
    def recorded_processing_runs(self) -> tuple[ProcessingRun, ...]:
        return tuple(self._processing_runs.added)

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
    assert unit_of_work.commit_count == 1
    assert unit_of_work.exit_exception is None

    document = unit_of_work.recorded_documents[0]
    processing_run = unit_of_work.recorded_processing_runs[0]
    assert document.id == DOCUMENT_ID
    assert document.accepted_at == ACCEPTED_AT
    assert processing_run.id == RUN_ID
    assert processing_run.document_id == DOCUMENT_ID
    assert processing_run.queued_at == ACCEPTED_AT


@pytest.mark.anyio
async def test_does_not_open_a_transaction_for_invalid_document_data() -> None:
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

    assert entered is False


@pytest.mark.anyio
async def test_does_not_commit_when_a_repository_write_fails() -> None:
    unit_of_work = RecordingUnitOfWork(fail_on_run_add=True)

    with pytest.raises(SimulatedPersistenceFailure):
        await handler(unit_of_work)(command())

    assert unit_of_work.commit_count == 0
    assert unit_of_work.exit_exception is SimulatedPersistenceFailure
