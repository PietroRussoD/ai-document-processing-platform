"""AI invoice proposal application-command tests."""

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from document_platform.application.commands.propose_invoice_fields import (
    InvoiceProposalDoesNotMatchRequest,
    InvoiceProposalGenerated,
    InvoiceProposalNotApplicable,
    InvoiceProposalRequiresClassification,
    InvoiceProposalRequiresSelectedText,
    InvoiceProposalRequiresTextSelection,
    ProposeInvoiceFields,
    ProposeInvoiceFieldsHandler,
)
from document_platform.application.ports import (
    InvoiceProposalOutcomeConflict,
    InvoiceProposalRequest,
    UnitOfWork,
)
from document_platform.application.ports.invoice_proposal_execution_repository import (
    AiInvoiceProposalExecutionAlreadyExists,
)
from document_platform.domain.processing import (
    AiInvoiceExtractionProposal,
    AiInvoiceProposalExecution,
    AiInvoiceProposalExecutionStatus,
    AiInvoiceProposalFailure,
    BusinessDocumentType,
    DocumentClassification,
    DocumentClassificationReason,
    DocumentOcrExtraction,
    DocumentTextExtraction,
    DocumentTextSelection,
    EmbeddedTextQuality,
    InvoiceModelProvider,
    InvoiceProposalGenerationFailureCode,
    InvoiceProposalStatus,
    OcrExtractionMethod,
    ProcessingTextSelectionReason,
    ProcessingTextSource,
    TextExtractionMethod,
)

AT = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
RUN_ID = UUID("c6c6c6c6-c6c6-46c6-86c6-c6c6c6c6c6c6")
SELECTED_TEXT = "Invoice number: INV-42\nTotal: EUR 12.50"


class ValueRepository:
    def __init__(self, value: object | None = None) -> None:
        self.value = value
        self.added: list[object] = []

    async def get(self, processing_run_id: UUID) -> object | None:
        return self.value

    async def add(self, value: object) -> None:
        self.value = value
        self.added.append(value)

    async def finish(self, value: object) -> None:
        self.value = value


class RecordingUnitOfWork:
    def __init__(self) -> None:
        self.active = False
        self.commit_count = 0
        self.invoice_proposals = ValueRepository()
        self.invoice_proposal_failures = ValueRepository()
        self.invoice_proposal_executions = ValueRepository()
        self.document_classifications = ValueRepository(
            DocumentClassification(
                processing_run_id=RUN_ID,
                document_type=BusinessDocumentType.INVOICE,
                reason=DocumentClassificationReason.KEYWORD_MATCHED,
                classified_at=AT,
            )
        )
        self.document_text_selections = ValueRepository(
            DocumentTextSelection(
                processing_run_id=RUN_ID,
                source=ProcessingTextSource.EMBEDDED,
                reason=ProcessingTextSelectionReason.EMBEDDED_SUFFICIENT,
                selected_at=AT,
            )
        )
        self.document_text_extractions = ValueRepository(
            DocumentTextExtraction(
                processing_run_id=RUN_ID,
                method=TextExtractionMethod.PYMUPDF,
                text=SELECTED_TEXT,
                page_count=1,
                character_count=len(SELECTED_TEXT),
                non_whitespace_character_count=sum(
                    not character.isspace() for character in SELECTED_TEXT
                ),
                quality=EmbeddedTextQuality.SUFFICIENT,
                extracted_at=AT,
            )
        )
        self.document_ocr_extractions = ValueRepository()

    async def __aenter__(self) -> Self:
        self.active = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.active = False

    async def commit(self) -> None:
        self.commit_count += 1


class RecordingGenerator:
    def __init__(self, unit_of_work: RecordingUnitOfWork) -> None:
        self.unit_of_work = unit_of_work
        self.requests: list[InvoiceProposalRequest] = []

    async def generate(self, request: InvoiceProposalRequest) -> AiInvoiceExtractionProposal:
        assert not self.unit_of_work.active
        self.requests.append(request)
        return proposal(request)


class MismatchedGenerator(RecordingGenerator):
    async def generate(self, request: InvoiceProposalRequest) -> AiInvoiceExtractionProposal:
        generated = proposal(request)
        return AiInvoiceExtractionProposal(
            processing_run_id=generated.processing_run_id,
            schema_version=generated.schema_version,
            provider=generated.provider,
            model_reference=generated.model_reference,
            model_digest=generated.model_digest,
            prompt_version=generated.prompt_version,
            selected_text_sha256="0" * 64,
            status=generated.status,
            invoice_number=generated.invoice_number,
            issue_date=generated.issue_date,
            supplier_name=generated.supplier_name,
            currency=generated.currency,
            total_amount=generated.total_amount,
            issues=generated.issues,
            proposed_at=generated.proposed_at,
        )


def proposal(request: InvoiceProposalRequest) -> AiInvoiceExtractionProposal:
    return AiInvoiceExtractionProposal(
        processing_run_id=request.processing_run_id,
        schema_version=1,
        provider=InvoiceModelProvider.OLLAMA,
        model_reference="qwen2.5:3b",
        model_digest=None,
        prompt_version="invoice-fields-v1",
        selected_text_sha256=request.selected_text_sha256,
        status=InvoiceProposalStatus.VALID,
        invoice_number="INV-42",
        issue_date=date(2026, 9, 27),
        supplier_name="Acme Ltd",
        currency="EUR",
        total_amount=Decimal("12.50"),
        issues=(),
        proposed_at=AT,
    )


def handler(
    unit_of_work: RecordingUnitOfWork,
    generator: RecordingGenerator,
) -> ProposeInvoiceFieldsHandler:
    return ProposeInvoiceFieldsHandler(
        unit_of_work_factory=lambda: cast(UnitOfWork, unit_of_work),
        proposal_generator=generator,
        clock=lambda: AT,
    )


@pytest.mark.anyio
async def test_generates_and_persists_a_proposal_outside_the_database_transaction() -> None:
    unit_of_work = RecordingUnitOfWork()
    generator = RecordingGenerator(unit_of_work)

    result = await handler(unit_of_work, generator)(ProposeInvoiceFields(RUN_ID))

    assert result == InvoiceProposalGenerated(proposal(generator.requests[0]), replayed=False)
    assert generator.requests[0].selected_text == SELECTED_TEXT
    assert (
        generator.requests[0].selected_text_sha256
        == hashlib.sha256(SELECTED_TEXT.encode("utf-8")).hexdigest()
    )
    assert len(unit_of_work.invoice_proposals.added) == 1
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_reuses_an_existing_proposal_without_calling_the_model() -> None:
    unit_of_work = RecordingUnitOfWork()
    generator = RecordingGenerator(unit_of_work)
    existing = proposal(InvoiceProposalRequest(RUN_ID, SELECTED_TEXT))
    unit_of_work.invoice_proposals.value = existing

    result = await handler(unit_of_work, generator)(ProposeInvoiceFields(RUN_ID))

    assert result == InvoiceProposalGenerated(existing, replayed=True)
    assert generator.requests == []
    assert unit_of_work.commit_count == 0


@pytest.mark.anyio
async def test_does_not_call_model_when_terminal_failure_is_recorded() -> None:
    unit_of_work = RecordingUnitOfWork()
    unit_of_work.invoice_proposal_failures.value = AiInvoiceProposalFailure(
        processing_run_id=RUN_ID,
        provider=InvoiceModelProvider.OLLAMA,
        model_reference="qwen3:8b",
        code=InvoiceProposalGenerationFailureCode.UNAVAILABLE,
        failed_at=AT,
    )
    generator = RecordingGenerator(unit_of_work)

    with pytest.raises(InvoiceProposalOutcomeConflict):
        await handler(unit_of_work, generator)(ProposeInvoiceFields(RUN_ID))

    assert generator.requests == []


@pytest.mark.anyio
async def test_rejects_a_non_invoice_document_before_calling_the_model() -> None:
    unit_of_work = RecordingUnitOfWork()
    unit_of_work.document_classifications.value = DocumentClassification(
        processing_run_id=RUN_ID,
        document_type=BusinessDocumentType.PURCHASE_ORDER,
        reason=DocumentClassificationReason.KEYWORD_MATCHED,
        classified_at=AT,
    )
    generator = RecordingGenerator(unit_of_work)

    with pytest.raises(InvoiceProposalNotApplicable):
        await handler(unit_of_work, generator)(ProposeInvoiceFields(RUN_ID))

    assert generator.requests == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("repository_name", "error_type"),
    [
        ("document_classifications", InvoiceProposalRequiresClassification),
        ("document_text_selections", InvoiceProposalRequiresTextSelection),
        ("document_text_extractions", InvoiceProposalRequiresSelectedText),
    ],
)
async def test_requires_classification_and_selected_canonical_text(
    repository_name: str,
    error_type: type[RuntimeError],
) -> None:
    unit_of_work = RecordingUnitOfWork()
    cast(ValueRepository, getattr(unit_of_work, repository_name)).value = None
    generator = RecordingGenerator(unit_of_work)

    with pytest.raises(error_type):
        await handler(unit_of_work, generator)(ProposeInvoiceFields(RUN_ID))

    assert generator.requests == []


@pytest.mark.anyio
async def test_reads_the_selected_ocr_text_when_ocr_was_chosen() -> None:
    unit_of_work = RecordingUnitOfWork()
    unit_of_work.document_text_selections.value = DocumentTextSelection(
        processing_run_id=RUN_ID,
        source=ProcessingTextSource.OCR,
        reason=ProcessingTextSelectionReason.OCR_HAS_MORE_TEXT,
        selected_at=AT,
    )
    unit_of_work.document_ocr_extractions.value = DocumentOcrExtraction(
        processing_run_id=RUN_ID,
        method=OcrExtractionMethod.TESSERACT,
        text="OCR-selected invoice text",
        page_count=1,
        character_count=len("OCR-selected invoice text"),
        non_whitespace_character_count=23,
        extracted_at=AT,
    )
    generator = RecordingGenerator(unit_of_work)

    await handler(unit_of_work, generator)(ProposeInvoiceFields(RUN_ID))

    assert generator.requests[0].selected_text == "OCR-selected invoice text"


@pytest.mark.anyio
async def test_rejects_a_proposal_for_different_source_text() -> None:
    unit_of_work = RecordingUnitOfWork()
    generator = MismatchedGenerator(unit_of_work)

    with pytest.raises(InvoiceProposalDoesNotMatchRequest):
        await handler(unit_of_work, generator)(ProposeInvoiceFields(RUN_ID))

    assert unit_of_work.invoice_proposals.added == []
    assert unit_of_work.commit_count == 0


@pytest.mark.anyio
@pytest.mark.parametrize("enabled", [False, True])
async def test_records_initial_execution_before_model_call(enabled: bool) -> None:
    unit_of_work = RecordingUnitOfWork()
    generator = RecordingGenerator(unit_of_work)

    proceed = await handler(unit_of_work, generator).begin_execution(
        ProposeInvoiceFields(RUN_ID), enabled=enabled
    )

    assert proceed is enabled
    assert unit_of_work.invoice_proposal_executions.value == AiInvoiceProposalExecution.begin(
        processing_run_id=RUN_ID, enabled=enabled, at=AT
    )
    assert generator.requests == []
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize("enabled", [False, True])
async def test_retry_keeps_existing_running_execution(enabled: bool) -> None:
    unit_of_work = RecordingUnitOfWork()
    initial = AiInvoiceProposalExecution.begin(processing_run_id=RUN_ID, enabled=True, at=AT)
    unit_of_work.invoice_proposal_executions.value = initial
    generator = RecordingGenerator(unit_of_work)

    assert await handler(unit_of_work, generator).begin_execution(
        ProposeInvoiceFields(RUN_ID), enabled=enabled
    )
    assert unit_of_work.invoice_proposal_executions.value is initial
    assert unit_of_work.commit_count == 0


@pytest.mark.anyio
@pytest.mark.parametrize("state", ["disabled", "completed", "failed"])
async def test_terminal_execution_does_not_restart(state: str) -> None:
    unit_of_work = RecordingUnitOfWork()
    initial = AiInvoiceProposalExecution.begin(
        processing_run_id=RUN_ID, enabled=state != "disabled", at=AT
    )
    if state == "completed":
        initial = initial.complete(at=AT)
    elif state == "failed":
        initial = initial.fail(at=AT)
    unit_of_work.invoice_proposal_executions.value = initial
    generator = RecordingGenerator(unit_of_work)

    assert not await handler(unit_of_work, generator).begin_execution(
        ProposeInvoiceFields(RUN_ID), enabled=True
    )
    assert unit_of_work.commit_count == 0


@pytest.mark.anyio
@pytest.mark.parametrize("outcome", ["invoice_proposals", "invoice_proposal_failures"])
async def test_legacy_outcome_does_not_create_historical_execution(outcome: str) -> None:
    unit_of_work = RecordingUnitOfWork()
    cast(ValueRepository, getattr(unit_of_work, outcome)).value = object()
    generator = RecordingGenerator(unit_of_work)

    assert not await handler(unit_of_work, generator).begin_execution(
        ProposeInvoiceFields(RUN_ID), enabled=True
    )
    assert unit_of_work.invoice_proposal_executions.value is None
    assert unit_of_work.commit_count == 0


@pytest.mark.anyio
async def test_proposal_and_completed_execution_share_one_commit() -> None:
    unit_of_work = RecordingUnitOfWork()
    generator = RecordingGenerator(unit_of_work)
    proposer = handler(unit_of_work, generator)
    await proposer.begin_execution(ProposeInvoiceFields(RUN_ID), enabled=True)

    await proposer(ProposeInvoiceFields(RUN_ID))

    execution = unit_of_work.invoice_proposal_executions.value
    assert isinstance(execution, AiInvoiceProposalExecution)
    assert execution.status is AiInvoiceProposalExecutionStatus.COMPLETED
    assert len(unit_of_work.invoice_proposals.added) == 1
    assert unit_of_work.commit_count == 2


@pytest.mark.anyio
@pytest.mark.parametrize("enabled", [False, True])
async def test_concurrent_initialization_uses_the_winning_execution(enabled: bool) -> None:
    class ContendedExecutionRepository(ValueRepository):
        async def add(self, value: object) -> None:
            self.value = AiInvoiceProposalExecution.begin(
                processing_run_id=RUN_ID, enabled=enabled, at=AT
            )
            raise AiInvoiceProposalExecutionAlreadyExists(RUN_ID)

    unit_of_work = RecordingUnitOfWork()
    unit_of_work.invoice_proposal_executions = ContendedExecutionRepository()
    generator = RecordingGenerator(unit_of_work)

    assert (
        await handler(unit_of_work, generator).begin_execution(
            ProposeInvoiceFields(RUN_ID), enabled=not enabled
        )
        is enabled
    )
    assert unit_of_work.commit_count == 0
