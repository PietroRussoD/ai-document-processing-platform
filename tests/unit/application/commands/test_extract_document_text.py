"""Embedded text extraction application tests."""

from datetime import UTC, datetime
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from document_platform.application.commands import (
    DocumentTextExtracted,
    ExtractDocumentText,
    ExtractDocumentTextHandler,
)
from document_platform.application.ports import ExtractedPdfText, StoredBlob, UnitOfWork
from document_platform.domain.documents import Document
from document_platform.domain.processing import (
    DocumentTextExtraction,
    ProcessingRun,
    TextExtractionMethod,
)

QUEUED_AT = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
EXTRACTED_AT = datetime(2026, 9, 15, 12, 1, tzinfo=UTC)
DOCUMENT_ID = UUID("51515151-5151-4151-8151-515151515151")
RUN_ID = UUID("52525252-5252-4252-8252-525252525252")


class RecordingDocumentRepository:
    def __init__(self, document: Document) -> None:
        self.document = document

    async def get(self, document_id: UUID) -> Document | None:
        return self.document if document_id == self.document.id else None


class RecordingProcessingRunRepository:
    def __init__(self, run: ProcessingRun) -> None:
        self.run = run

    async def get(self, run_id: UUID) -> ProcessingRun | None:
        return self.run if run_id == self.run.id else None


class RecordingExtractionRepository:
    def __init__(self) -> None:
        self.extraction: DocumentTextExtraction | None = None
        self.added: list[DocumentTextExtraction] = []

    async def add(self, extraction: DocumentTextExtraction) -> None:
        self.extraction = extraction
        self.added.append(extraction)

    async def get(self, processing_run_id: UUID) -> DocumentTextExtraction | None:
        if self.extraction is None or processing_run_id != self.extraction.processing_run_id:
            return None
        return self.extraction


class RecordingUnitOfWork:
    def __init__(self) -> None:
        document = Document.accept_pdf(
            document_id=DOCUMENT_ID,
            original_filename="supplier-invoice.pdf",
            size_bytes=42,
            page_count=1,
            content_sha256="a" * 64,
            storage_key="blobs/sha256/aa/" + "a" * 64,
            accepted_at=QUEUED_AT,
        ).start_processing(at=QUEUED_AT)
        self.documents = RecordingDocumentRepository(document)
        self.processing_runs = RecordingProcessingRunRepository(
            ProcessingRun.queue(run_id=RUN_ID, document_id=DOCUMENT_ID, queued_at=QUEUED_AT).start(
                at=QUEUED_AT
            )
        )
        self.document_text_extractions = RecordingExtractionRepository()
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


class RecordingBlobStore:
    def __init__(self) -> None:
        self.load_calls: list[str] = []

    async def store(self, source: object) -> StoredBlob:
        raise AssertionError("not used")

    async def load(self, key: str) -> bytes:
        self.load_calls.append(key)
        return b"synthetic PDF"


class RecordingExtractor:
    def __init__(self) -> None:
        self.contents: list[bytes] = []

    async def extract(self, content: bytes) -> ExtractedPdfText:
        self.contents.append(content)
        return ExtractedPdfText(
            text="Invoice 42",
            page_count=1,
            character_count=10,
            non_whitespace_character_count=9,
        )


def handler(
    unit_of_work: RecordingUnitOfWork,
    blob_store: RecordingBlobStore,
    extractor: RecordingExtractor,
) -> ExtractDocumentTextHandler:
    return ExtractDocumentTextHandler(
        unit_of_work_factory=lambda: cast(UnitOfWork, unit_of_work),
        blob_store=blob_store,  # type: ignore[arg-type]
        pdf_text_extractor=extractor,  # type: ignore[arg-type]
        clock=lambda: EXTRACTED_AT,
    )


@pytest.mark.anyio
async def test_extracts_and_persists_embedded_text_once() -> None:
    unit_of_work = RecordingUnitOfWork()
    blob_store = RecordingBlobStore()
    extractor = RecordingExtractor()

    result = await handler(unit_of_work, blob_store, extractor)(ExtractDocumentText(RUN_ID))

    assert result == DocumentTextExtracted(RUN_ID, 10, 9, replayed=False)
    assert unit_of_work.commit_count == 1
    assert unit_of_work.document_text_extractions.added[0].method is TextExtractionMethod.PYMUPDF
    assert unit_of_work.document_text_extractions.added[0].text == "Invoice 42"


@pytest.mark.anyio
async def test_replay_reuses_persisted_text_without_loading_the_document() -> None:
    unit_of_work = RecordingUnitOfWork()
    blob_store = RecordingBlobStore()
    extractor = RecordingExtractor()
    command = ExtractDocumentText(RUN_ID)

    await handler(unit_of_work, blob_store, extractor)(command)
    replay = await handler(unit_of_work, blob_store, extractor)(command)

    assert replay == DocumentTextExtracted(RUN_ID, 10, 9, replayed=True)
    assert len(blob_store.load_calls) == 1
    assert len(extractor.contents) == 1
    assert unit_of_work.commit_count == 1
