"""Extract and durably record embedded text for a processing run."""

from dataclasses import dataclass
from uuid import UUID

from document_platform.application.ports import (
    BlobStore,
    Clock,
    DocumentTextExtractionAlreadyExists,
    ParserExecutionFailed,
    PdfTextExtractor,
    UnitOfWorkFactory,
)
from document_platform.domain.processing import (
    DocumentTextExtraction,
    EmbeddedTextQualityPolicy,
    ProcessingRunStatus,
    TextExtractionMethod,
)


@dataclass(frozen=True, slots=True)
class ExtractDocumentText:
    processing_run_id: UUID


@dataclass(frozen=True, slots=True)
class DocumentTextExtracted:
    processing_run_id: UUID
    character_count: int
    non_whitespace_character_count: int
    replayed: bool


class TextExtractionRunNotFound(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"processing run not found for text extraction: {processing_run_id}")


class TextExtractionDocumentNotFound(RuntimeError):
    def __init__(self, document_id: UUID) -> None:
        super().__init__(f"document not found for text extraction: {document_id}")


class InvalidTextExtractionRun(RuntimeError):
    def __init__(self, processing_run_id: UUID, status: ProcessingRunStatus) -> None:
        super().__init__(f"processing run cannot extract text from {status}: {processing_run_id}")


class ExtractDocumentTextHandler:
    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        blob_store: BlobStore,
        pdf_text_extractor: PdfTextExtractor,
        embedded_text_quality_policy: EmbeddedTextQualityPolicy,
        clock: Clock,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._blob_store = blob_store
        self._pdf_text_extractor = pdf_text_extractor
        self._embedded_text_quality_policy = embedded_text_quality_policy
        self._clock = clock

    async def __call__(self, command: ExtractDocumentText) -> DocumentTextExtracted:
        async with self._unit_of_work_factory() as unit_of_work:
            existing = await unit_of_work.document_text_extractions.get(command.processing_run_id)
            if existing is not None:
                return _result(existing, replayed=True)

            run = await unit_of_work.processing_runs.get(command.processing_run_id)
            if run is None:
                raise TextExtractionRunNotFound(command.processing_run_id)
            if run.status is not ProcessingRunStatus.RUNNING:
                raise InvalidTextExtractionRun(run.id, run.status)

            document = await unit_of_work.documents.get(run.document_id)
            if document is None:
                raise TextExtractionDocumentNotFound(run.document_id)

        extracted = await self._pdf_text_extractor.extract(
            await self._blob_store.load(document.storage_key)
        )
        extraction = DocumentTextExtraction(
            processing_run_id=command.processing_run_id,
            method=TextExtractionMethod.PYMUPDF,
            text=extracted.text,
            page_count=extracted.page_count,
            character_count=extracted.character_count,
            non_whitespace_character_count=extracted.non_whitespace_character_count,
            quality=self._embedded_text_quality_policy.assess(
                non_whitespace_character_count=extracted.non_whitespace_character_count
            ),
            extracted_at=self._clock(),
        )

        try:
            async with self._unit_of_work_factory() as unit_of_work:
                existing = await unit_of_work.document_text_extractions.get(
                    command.processing_run_id
                )
                if existing is not None:
                    return _result(existing, replayed=True)
                stored_document = await unit_of_work.documents.get_for_update(document.id)
                if stored_document is None:
                    raise TextExtractionDocumentNotFound(document.id)
                try:
                    updated_document = stored_document.record_page_count(extracted.page_count)
                except ValueError:
                    raise ParserExecutionFailed(
                        "Parser page count did not match the stored document"
                    ) from None
                if updated_document is not stored_document:
                    await unit_of_work.documents.update(updated_document)
                await unit_of_work.document_text_extractions.add(extraction)
                await unit_of_work.commit()
        except DocumentTextExtractionAlreadyExists:
            return await self._existing_result(command.processing_run_id)

        return _result(extraction, replayed=False)

    async def _existing_result(self, processing_run_id: UUID) -> DocumentTextExtracted:
        async with self._unit_of_work_factory() as unit_of_work:
            existing = await unit_of_work.document_text_extractions.get(processing_run_id)
            if existing is None:
                raise RuntimeError("text extraction conflict without a persisted record")
            return _result(existing, replayed=True)


def _result(extraction: DocumentTextExtraction, *, replayed: bool) -> DocumentTextExtracted:
    return DocumentTextExtracted(
        processing_run_id=extraction.processing_run_id,
        character_count=extraction.character_count,
        non_whitespace_character_count=extraction.non_whitespace_character_count,
        replayed=replayed,
    )
