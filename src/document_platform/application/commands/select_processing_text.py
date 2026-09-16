"""Select and persist canonical text for downstream processing."""

from dataclasses import dataclass
from uuid import UUID

from document_platform.application.ports import (
    Clock,
    DocumentTextSelectionAlreadyExists,
    UnitOfWorkFactory,
)
from document_platform.domain.processing import ProcessingTextSelectionPolicy


@dataclass(frozen=True, slots=True)
class SelectProcessingText:
    processing_run_id: UUID


@dataclass(frozen=True, slots=True)
class ProcessingTextSelected:
    processing_run_id: UUID
    replayed: bool


class ProcessingTextSelectionRequiresEmbeddedText(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"embedded text extraction is missing: {processing_run_id}")


class SelectProcessingTextHandler:
    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        selection_policy: ProcessingTextSelectionPolicy,
        clock: Clock,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._selection_policy = selection_policy
        self._clock = clock

    async def __call__(self, command: SelectProcessingText) -> ProcessingTextSelected:
        async with self._unit_of_work_factory() as unit_of_work:
            existing = await unit_of_work.document_text_selections.get(command.processing_run_id)
            if existing is not None:
                return ProcessingTextSelected(command.processing_run_id, replayed=True)
            embedded = await unit_of_work.document_text_extractions.get(command.processing_run_id)
            if embedded is None:
                raise ProcessingTextSelectionRequiresEmbeddedText(command.processing_run_id)
            ocr = await unit_of_work.document_ocr_extractions.get(command.processing_run_id)
            selection = self._selection_policy.select(
                embedded=embedded,
                ocr=ocr,
                selected_at=self._clock(),
            )
            try:
                await unit_of_work.document_text_selections.add(selection)
                await unit_of_work.commit()
            except DocumentTextSelectionAlreadyExists:
                return ProcessingTextSelected(command.processing_run_id, replayed=True)
            return ProcessingTextSelected(command.processing_run_id, replayed=False)
