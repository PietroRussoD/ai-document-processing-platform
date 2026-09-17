"""Extract and persist structured invoice data from canonical text."""

from dataclasses import dataclass
from uuid import UUID

from document_platform.application.ports import (
    Clock,
    InvoiceExtractionAlreadyExists,
    UnitOfWorkFactory,
)
from document_platform.domain.processing import (
    BusinessDocumentType,
    DeterministicInvoiceExtractionPolicy,
    ProcessingTextSource,
)


@dataclass(frozen=True, slots=True)
class ExtractInvoice:
    processing_run_id: UUID


@dataclass(frozen=True, slots=True)
class InvoiceExtracted:
    processing_run_id: UUID
    replayed: bool


class InvoiceExtractionRequiresClassification(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"document classification is missing: {processing_run_id}")


class InvoiceExtractionNotApplicable(RuntimeError):
    def __init__(self, processing_run_id: UUID, document_type: BusinessDocumentType) -> None:
        super().__init__(
            f"invoice extraction is not applicable to {document_type}: {processing_run_id}"
        )


class InvoiceExtractionRequiresTextSelection(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"canonical text selection is missing: {processing_run_id}")


class InvoiceExtractionRequiresSelectedText(RuntimeError):
    def __init__(self, processing_run_id: UUID, source: ProcessingTextSource) -> None:
        super().__init__(f"selected {source} text is missing: {processing_run_id}")


class ExtractInvoiceHandler:
    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        extraction_policy: DeterministicInvoiceExtractionPolicy,
        clock: Clock,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._extraction_policy = extraction_policy
        self._clock = clock

    async def __call__(self, command: ExtractInvoice) -> InvoiceExtracted:
        async with self._unit_of_work_factory() as unit_of_work:
            existing = await unit_of_work.invoice_extractions.get(command.processing_run_id)
            if existing is not None:
                return InvoiceExtracted(command.processing_run_id, replayed=True)
            classification = await unit_of_work.document_classifications.get(
                command.processing_run_id
            )
            if classification is None:
                raise InvoiceExtractionRequiresClassification(command.processing_run_id)
            if classification.document_type is not BusinessDocumentType.INVOICE:
                raise InvoiceExtractionNotApplicable(
                    command.processing_run_id,
                    classification.document_type,
                )
            selection = await unit_of_work.document_text_selections.get(command.processing_run_id)
            if selection is None:
                raise InvoiceExtractionRequiresTextSelection(command.processing_run_id)
            if selection.source is ProcessingTextSource.EMBEDDED:
                selected_text = await unit_of_work.document_text_extractions.get(
                    command.processing_run_id
                )
            else:
                selected_text = await unit_of_work.document_ocr_extractions.get(
                    command.processing_run_id
                )
            if selected_text is None:
                raise InvoiceExtractionRequiresSelectedText(
                    command.processing_run_id,
                    selection.source,
                )
            extraction = self._extraction_policy.extract(
                processing_run_id=command.processing_run_id,
                text=selected_text.text,
                extracted_at=self._clock(),
            )
            try:
                await unit_of_work.invoice_extractions.add(extraction)
                await unit_of_work.commit()
            except InvoiceExtractionAlreadyExists:
                return InvoiceExtracted(command.processing_run_id, replayed=True)
            return InvoiceExtracted(command.processing_run_id, replayed=False)
