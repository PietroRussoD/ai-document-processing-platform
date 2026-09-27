"""Generate and persist an immutable AI proposal from canonical invoice text."""

from dataclasses import dataclass
from uuid import UUID

from document_platform.application.ports import (
    InvoiceProposalAlreadyExists,
    InvoiceProposalGenerator,
    InvoiceProposalOutcomeConflict,
    InvoiceProposalRequest,
    UnitOfWorkFactory,
)
from document_platform.domain.processing import (
    AiInvoiceExtractionProposal,
    BusinessDocumentType,
    ProcessingTextSource,
)


@dataclass(frozen=True, slots=True)
class ProposeInvoiceFields:
    processing_run_id: UUID


@dataclass(frozen=True, slots=True)
class InvoiceProposalGenerated:
    proposal: AiInvoiceExtractionProposal
    replayed: bool


class InvoiceProposalRequiresClassification(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"document classification is missing: {processing_run_id}")


class InvoiceProposalNotApplicable(RuntimeError):
    def __init__(self, processing_run_id: UUID, document_type: BusinessDocumentType) -> None:
        super().__init__(
            f"AI invoice proposal is not applicable to {document_type}: {processing_run_id}"
        )


class InvoiceProposalRequiresTextSelection(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"canonical text selection is missing: {processing_run_id}")


class InvoiceProposalRequiresSelectedText(RuntimeError):
    def __init__(self, processing_run_id: UUID, source: ProcessingTextSource) -> None:
        super().__init__(f"selected {source} text is missing: {processing_run_id}")


class InvoiceProposalDoesNotMatchRequest(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"generated proposal does not match request: {processing_run_id}")


class ProposeInvoiceFieldsHandler:
    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        proposal_generator: InvoiceProposalGenerator,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._proposal_generator = proposal_generator

    async def __call__(self, command: ProposeInvoiceFields) -> InvoiceProposalGenerated:
        async with self._unit_of_work_factory() as unit_of_work:
            existing = await unit_of_work.invoice_proposals.get(command.processing_run_id)
            if existing is not None:
                return InvoiceProposalGenerated(existing, replayed=True)
            if await unit_of_work.invoice_proposal_failures.get(command.processing_run_id):
                raise InvoiceProposalOutcomeConflict(command.processing_run_id)

            classification = await unit_of_work.document_classifications.get(
                command.processing_run_id
            )
            if classification is None:
                raise InvoiceProposalRequiresClassification(command.processing_run_id)
            if classification.document_type is not BusinessDocumentType.INVOICE:
                raise InvoiceProposalNotApplicable(
                    command.processing_run_id,
                    classification.document_type,
                )

            selection = await unit_of_work.document_text_selections.get(command.processing_run_id)
            if selection is None:
                raise InvoiceProposalRequiresTextSelection(command.processing_run_id)
            if selection.source is ProcessingTextSource.EMBEDDED:
                selected_text = await unit_of_work.document_text_extractions.get(
                    command.processing_run_id
                )
            else:
                selected_text = await unit_of_work.document_ocr_extractions.get(
                    command.processing_run_id
                )
            if selected_text is None:
                raise InvoiceProposalRequiresSelectedText(
                    command.processing_run_id,
                    selection.source,
                )
            request = InvoiceProposalRequest(
                processing_run_id=command.processing_run_id,
                selected_text=selected_text.text,
            )

        proposal = await self._proposal_generator.generate(request)
        if (
            proposal.processing_run_id != request.processing_run_id
            or proposal.selected_text_sha256 != request.selected_text_sha256
        ):
            raise InvoiceProposalDoesNotMatchRequest(command.processing_run_id)
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                await unit_of_work.invoice_proposals.add(proposal)
                await unit_of_work.commit()
        except InvoiceProposalAlreadyExists:
            async with self._unit_of_work_factory() as unit_of_work:
                existing = await unit_of_work.invoice_proposals.get(command.processing_run_id)
            if existing is not None:
                return InvoiceProposalGenerated(existing, replayed=True)
            raise
        return InvoiceProposalGenerated(proposal, replayed=False)
