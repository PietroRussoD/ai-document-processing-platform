"""Perform and persist OCR only when embedded text needs it."""

from dataclasses import dataclass
from uuid import UUID

from document_platform.application.ports import (
    BlobStore,
    Clock,
    DocumentOcrExtractionAlreadyExists,
    PdfOcrExtractor,
    UnitOfWorkFactory,
)
from document_platform.domain.processing import (
    DocumentOcrExtraction,
    EmbeddedTextQuality,
    OcrExtractionMethod,
    ProcessingRunStatus,
)


@dataclass(frozen=True, slots=True)
class ExtractOcrText:
    processing_run_id: UUID


@dataclass(frozen=True, slots=True)
class OcrTextExtractionResult:
    processing_run_id: UUID
    performed: bool
    replayed: bool


class OcrExtractionRunNotFound(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"processing run not found for OCR extraction: {processing_run_id}")


class OcrExtractionDocumentNotFound(RuntimeError):
    def __init__(self, document_id: UUID) -> None:
        super().__init__(f"document not found for OCR extraction: {document_id}")


class OcrExtractionRequiresEmbeddedText(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"embedded text extraction is missing: {processing_run_id}")


class InvalidOcrExtractionRun(RuntimeError):
    def __init__(self, processing_run_id: UUID, status: ProcessingRunStatus) -> None:
        super().__init__(
            f"processing run cannot extract OCR text from {status}: {processing_run_id}"
        )


class ExtractOcrTextHandler:
    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        blob_store: BlobStore,
        pdf_ocr_extractor: PdfOcrExtractor,
        clock: Clock,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._blob_store = blob_store
        self._pdf_ocr_extractor = pdf_ocr_extractor
        self._clock = clock

    async def __call__(self, command: ExtractOcrText) -> OcrTextExtractionResult:
        async with self._unit_of_work_factory() as unit_of_work:
            existing = await unit_of_work.document_ocr_extractions.get(command.processing_run_id)
            if existing is not None:
                return OcrTextExtractionResult(
                    command.processing_run_id,
                    performed=True,
                    replayed=True,
                )

            embedded = await unit_of_work.document_text_extractions.get(command.processing_run_id)
            if embedded is None:
                raise OcrExtractionRequiresEmbeddedText(command.processing_run_id)
            if embedded.quality is EmbeddedTextQuality.SUFFICIENT:
                return OcrTextExtractionResult(
                    command.processing_run_id,
                    performed=False,
                    replayed=False,
                )

            run = await unit_of_work.processing_runs.get(command.processing_run_id)
            if run is None:
                raise OcrExtractionRunNotFound(command.processing_run_id)
            if run.status is not ProcessingRunStatus.RUNNING:
                raise InvalidOcrExtractionRun(run.id, run.status)
            document = await unit_of_work.documents.get(run.document_id)
            if document is None:
                raise OcrExtractionDocumentNotFound(run.document_id)

        content = await self._blob_store.load(document.storage_key)
        extracted = await self._pdf_ocr_extractor.extract(content)
        extraction = DocumentOcrExtraction(
            processing_run_id=command.processing_run_id,
            method=OcrExtractionMethod.TESSERACT,
            text=extracted.text,
            page_count=extracted.page_count,
            character_count=extracted.character_count,
            non_whitespace_character_count=extracted.non_whitespace_character_count,
            extracted_at=self._clock(),
        )
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                existing = await unit_of_work.document_ocr_extractions.get(
                    command.processing_run_id
                )
                if existing is not None:
                    return OcrTextExtractionResult(
                        command.processing_run_id,
                        performed=True,
                        replayed=True,
                    )
                await unit_of_work.document_ocr_extractions.add(extraction)
                await unit_of_work.commit()
        except DocumentOcrExtractionAlreadyExists:
            return await self._existing_result(command.processing_run_id)

        return OcrTextExtractionResult(command.processing_run_id, performed=True, replayed=False)

    async def _existing_result(self, processing_run_id: UUID) -> OcrTextExtractionResult:
        async with self._unit_of_work_factory() as unit_of_work:
            existing = await unit_of_work.document_ocr_extractions.get(processing_run_id)
            if existing is None:
                raise RuntimeError("OCR extraction conflict without a persisted record")
            return OcrTextExtractionResult(processing_run_id, performed=True, replayed=True)
