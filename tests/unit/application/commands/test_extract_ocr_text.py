"""Conditional OCR extraction application tests."""

from datetime import UTC, datetime
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from document_platform.application.commands import (
    ExtractOcrText,
    ExtractOcrTextHandler,
    OcrTextExtractionResult,
)
from document_platform.application.ports import (
    ExtractedOcrText,
    StoredBlob,
    UnitOfWork,
)
from document_platform.domain.documents import Document
from document_platform.domain.processing import (
    DocumentOcrExtraction,
    DocumentTextExtraction,
    EmbeddedTextQuality,
    OcrExtractionMethod,
    ProcessingRun,
    TextExtractionMethod,
)

QUEUED_AT = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
EXTRACTED_AT = datetime(2026, 9, 15, 12, 1, tzinfo=UTC)
DOCUMENT_ID = UUID("71717171-7171-4171-8171-717171717171")
RUN_ID = UUID("72727272-7272-4272-8272-727272727272")


class DocumentRepository:
    def __init__(self, document: Document) -> None:
        self.document = document

    async def get(self, document_id: UUID) -> Document | None:
        return self.document if document_id == self.document.id else None

    async def get_for_update(self, document_id: UUID) -> Document | None:
        return await self.get(document_id)

    async def update(self, document: Document) -> None:
        self.document = document


class ProcessingRunRepository:
    def __init__(self, run: ProcessingRun) -> None:
        self.run = run

    async def get(self, run_id: UUID) -> ProcessingRun | None:
        return self.run if run_id == self.run.id else None


class TextRepository:
    def __init__(self, extraction: DocumentTextExtraction) -> None:
        self.extraction = extraction

    async def get(self, processing_run_id: UUID) -> DocumentTextExtraction | None:
        return self.extraction if processing_run_id == self.extraction.processing_run_id else None


class OcrRepository:
    def __init__(self) -> None:
        self.extraction: DocumentOcrExtraction | None = None
        self.added: list[DocumentOcrExtraction] = []

    async def add(self, extraction: DocumentOcrExtraction) -> None:
        self.extraction = extraction
        self.added.append(extraction)

    async def get(self, processing_run_id: UUID) -> DocumentOcrExtraction | None:
        if self.extraction is None or processing_run_id != self.extraction.processing_run_id:
            return None
        return self.extraction


class RecordingUnitOfWork:
    def __init__(self, *, quality: EmbeddedTextQuality) -> None:
        document = Document.accept_pdf(
            document_id=DOCUMENT_ID,
            original_filename="scanned-invoice.pdf",
            size_bytes=42,
            page_count=1,
            content_sha256="a" * 64,
            storage_key="blobs/sha256/aa/" + "a" * 64,
            accepted_at=QUEUED_AT,
        ).start_processing(at=QUEUED_AT)
        self.documents = DocumentRepository(document)
        self.processing_runs = ProcessingRunRepository(
            ProcessingRun.queue(run_id=RUN_ID, document_id=DOCUMENT_ID, queued_at=QUEUED_AT).start(
                at=QUEUED_AT
            )
        )
        self.document_text_extractions = TextRepository(
            DocumentTextExtraction(
                processing_run_id=RUN_ID,
                method=TextExtractionMethod.PYMUPDF,
                text="",
                page_count=1,
                character_count=0,
                non_whitespace_character_count=0,
                quality=quality,
                extracted_at=EXTRACTED_AT,
            )
        )
        self.document_ocr_extractions = OcrRepository()
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


class BlobStore:
    def __init__(self) -> None:
        self.load_calls = 0

    async def store(self, source: object) -> StoredBlob:
        raise AssertionError("not used")

    async def load(self, key: str) -> bytes:
        self.load_calls += 1
        return b"synthetic PDF"


class OcrExtractor:
    def __init__(self) -> None:
        self.calls = 0

    async def extract(self, content: bytes) -> ExtractedOcrText:
        self.calls += 1
        return ExtractedOcrText(
            text="Invoice 42",
            page_count=1,
            character_count=10,
            non_whitespace_character_count=9,
        )


def handler(
    unit_of_work: RecordingUnitOfWork,
    blob_store: BlobStore,
    ocr_extractor: OcrExtractor,
) -> ExtractOcrTextHandler:
    return ExtractOcrTextHandler(
        unit_of_work_factory=lambda: cast(UnitOfWork, unit_of_work),
        blob_store=blob_store,  # type: ignore[arg-type]
        pdf_ocr_extractor=ocr_extractor,  # type: ignore[arg-type]
        clock=lambda: EXTRACTED_AT,
    )


@pytest.mark.anyio
async def test_skips_ocr_when_embedded_text_is_sufficient() -> None:
    unit_of_work = RecordingUnitOfWork(quality=EmbeddedTextQuality.SUFFICIENT)
    blob_store = BlobStore()
    ocr_extractor = OcrExtractor()

    result = await handler(unit_of_work, blob_store, ocr_extractor)(ExtractOcrText(RUN_ID))

    assert result == OcrTextExtractionResult(RUN_ID, performed=False, replayed=False)
    assert blob_store.load_calls == 0
    assert ocr_extractor.calls == 0
    assert unit_of_work.commit_count == 0


@pytest.mark.anyio
async def test_extracts_and_persists_ocr_when_recommended() -> None:
    unit_of_work = RecordingUnitOfWork(quality=EmbeddedTextQuality.OCR_RECOMMENDED)
    blob_store = BlobStore()
    ocr_extractor = OcrExtractor()

    result = await handler(unit_of_work, blob_store, ocr_extractor)(ExtractOcrText(RUN_ID))

    assert result == OcrTextExtractionResult(RUN_ID, performed=True, replayed=False)
    assert unit_of_work.document_ocr_extractions.added[0].method is OcrExtractionMethod.TESSERACT
    assert blob_store.load_calls == 1
    assert ocr_extractor.calls == 1


@pytest.mark.anyio
async def test_replay_reuses_persisted_ocr_without_repeating_work() -> None:
    unit_of_work = RecordingUnitOfWork(quality=EmbeddedTextQuality.OCR_RECOMMENDED)
    blob_store = BlobStore()
    ocr_extractor = OcrExtractor()
    command = ExtractOcrText(RUN_ID)

    await handler(unit_of_work, blob_store, ocr_extractor)(command)
    replay = await handler(unit_of_work, blob_store, ocr_extractor)(command)

    assert replay == OcrTextExtractionResult(RUN_ID, performed=True, replayed=True)
    assert blob_store.load_calls == 1
    assert ocr_extractor.calls == 1
