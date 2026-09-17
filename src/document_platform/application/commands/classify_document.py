"""Classify the canonical processing text and persist the outcome."""

from dataclasses import dataclass
from uuid import UUID

from document_platform.application.ports import (
    Clock,
    DocumentClassificationAlreadyExists,
    UnitOfWorkFactory,
)
from document_platform.domain.processing import (
    BusinessDocumentType,
    DocumentClassificationPolicy,
    ProcessingTextSource,
)


@dataclass(frozen=True, slots=True)
class ClassifyDocument:
    processing_run_id: UUID


@dataclass(frozen=True, slots=True)
class DocumentClassified:
    processing_run_id: UUID
    replayed: bool
    document_type: BusinessDocumentType


class ClassificationRequiresTextSelection(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"canonical text selection is missing: {processing_run_id}")


class ClassificationRequiresSelectedText(RuntimeError):
    def __init__(self, processing_run_id: UUID, source: ProcessingTextSource) -> None:
        super().__init__(f"selected {source} text is missing: {processing_run_id}")


class ClassifyDocumentHandler:
    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        classification_policy: DocumentClassificationPolicy,
        clock: Clock,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._classification_policy = classification_policy
        self._clock = clock

    async def __call__(self, command: ClassifyDocument) -> DocumentClassified:
        async with self._unit_of_work_factory() as unit_of_work:
            existing = await unit_of_work.document_classifications.get(command.processing_run_id)
            if existing is not None:
                return DocumentClassified(
                    command.processing_run_id,
                    replayed=True,
                    document_type=existing.document_type,
                )
            selection = await unit_of_work.document_text_selections.get(command.processing_run_id)
            if selection is None:
                raise ClassificationRequiresTextSelection(command.processing_run_id)
            if selection.source is ProcessingTextSource.EMBEDDED:
                extraction = await unit_of_work.document_text_extractions.get(
                    command.processing_run_id
                )
            else:
                extraction = await unit_of_work.document_ocr_extractions.get(
                    command.processing_run_id
                )
            if extraction is None:
                raise ClassificationRequiresSelectedText(
                    command.processing_run_id, selection.source
                )
            classification = self._classification_policy.classify(
                processing_run_id=command.processing_run_id,
                text=extraction.text,
                classified_at=self._clock(),
            )
            try:
                await unit_of_work.document_classifications.add(classification)
                await unit_of_work.commit()
            except DocumentClassificationAlreadyExists:
                persisted = await unit_of_work.document_classifications.get(
                    command.processing_run_id
                )
                if persisted is None:
                    raise
                return DocumentClassified(
                    command.processing_run_id,
                    replayed=True,
                    document_type=persisted.document_type,
                )
            return DocumentClassified(
                command.processing_run_id,
                replayed=False,
                document_type=classification.document_type,
            )
