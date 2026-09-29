"""PostgreSQL document-status read-model integration tests."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.inbound.http.documents import DocumentStatusResponse
from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.adapters.outbound.postgresql.queries import SqlAlchemyDocumentStatusReader
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyAiInvoiceExtractionProposalRepository,
    SqlAlchemyAiInvoiceProposalExecutionRepository,
    SqlAlchemyAiInvoiceProposalFailureRepository,
    SqlAlchemyDocumentClassificationRepository,
    SqlAlchemyDocumentOcrExtractionRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyDocumentTextExtractionRepository,
    SqlAlchemyDocumentTextSelectionRepository,
    SqlAlchemyInvoiceExtractionRepository,
    SqlAlchemyInvoiceReviewCorrectionRepository,
    SqlAlchemyInvoiceValidationRepository,
    SqlAlchemyProcessingRunRepository,
    SqlAlchemyReviewResolutionRepository,
)
from document_platform.domain.documents import Document
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
    InvoiceExtraction,
    InvoiceExtractionMethod,
    InvoiceModelProvider,
    InvoiceProposalField,
    InvoiceProposalGenerationFailureCode,
    InvoiceProposalIssue,
    InvoiceProposalIssueCode,
    InvoiceProposalStatus,
    InvoiceReviewCorrection,
    InvoiceReviewCorrectionSource,
    InvoiceReviewField,
    InvoiceReviewFieldCorrection,
    InvoiceValidation,
    InvoiceValidationDecision,
    OcrExtractionMethod,
    ProcessingFailure,
    ProcessingFailureCode,
    ProcessingRun,
    ProcessingRunStatus,
    ProcessingStage,
    ProcessingTextSelectionReason,
    ProcessingTextSource,
    ReviewResolution,
    ReviewResolutionDecision,
    TextExtractionMethod,
)
from document_platform.settings import Settings

ACCEPTED_AT = datetime(2026, 9, 14, 12, 0, tzinfo=UTC)


@pytest.mark.anyio
async def test_returns_the_document_with_its_most_recent_run(
    migrated_postgres_url: str,
) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    document_id = uuid4()
    first_run_id = uuid4()
    latest_run_id = uuid4()
    document = Document.accept_pdf(
        document_id=document_id,
        original_filename="supplier-invoice.pdf",
        size_bytes=42_000,
        page_count=2,
        content_sha256="b" * 64,
        storage_key="blobs/sha256/bb/" + "b" * 64,
        accepted_at=ACCEPTED_AT,
    )
    first_run = (
        ProcessingRun.queue(
            run_id=first_run_id,
            document_id=document_id,
            queued_at=ACCEPTED_AT,
        )
        .start(at=ACCEPTED_AT + timedelta(seconds=1))
        .complete(at=ACCEPTED_AT + timedelta(seconds=2))
    )
    latest_run = ProcessingRun.queue(
        run_id=latest_run_id,
        document_id=document_id,
        queued_at=ACCEPTED_AT + timedelta(minutes=5),
        previous_run_id=first_run_id,
    )

    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            runs = SqlAlchemyProcessingRunRepository(session)
            await runs.add(first_run)
            await SqlAlchemyAiInvoiceProposalExecutionRepository(session).add(
                AiInvoiceProposalExecution.begin(
                    processing_run_id=first_run_id,
                    enabled=False,
                    at=ACCEPTED_AT + timedelta(seconds=2),
                )
            )
            await runs.add(latest_run)

        reader = SqlAlchemyDocumentStatusReader(database.sessions)
        result = await reader.get(document_id)
        missing = await reader.get(uuid4())
    finally:
        await database.dispose()

    assert result is not None
    assert result.id == document_id
    assert result.original_filename == "supplier-invoice.pdf"
    assert result.current_run.id == latest_run_id
    assert result.current_run.previous_run_id == first_run_id
    assert result.current_run.queued_at == latest_run.queued_at
    assert result.current_run.failure is None
    assert result.current_run.processing_output is None
    assert result.current_run.ai_proposal is None
    assert result.current_run.ai_proposal_failure is None
    assert result.current_run.ai_execution is None
    assert (
        DocumentStatusResponse.model_validate(result).model_dump(mode="json")["current_run"][
            "ai_execution"
        ]
        is None
    )
    assert missing is None


@pytest.mark.anyio
async def test_returns_ai_proposal_without_source_text_or_prompt(
    migrated_postgres_url: str,
) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    document_id = uuid4()
    run_id = uuid4()
    document = Document.accept_pdf(
        document_id=document_id,
        original_filename="proposal.pdf",
        size_bytes=100,
        page_count=1,
        content_sha256="a" * 64,
        storage_key="blobs/proposal",
        accepted_at=ACCEPTED_AT,
    )
    proposal = AiInvoiceExtractionProposal(
        processing_run_id=run_id,
        schema_version=1,
        provider=InvoiceModelProvider.OLLAMA,
        model_reference="qwen3:8b",
        model_digest=None,
        prompt_version="invoice-v1",
        selected_text_sha256="b" * 64,
        status=InvoiceProposalStatus.PARTIAL,
        invoice_number="INV-42",
        issue_date=None,
        supplier_name=None,
        currency=None,
        total_amount=None,
        issues=(
            InvoiceProposalIssue(
                code=InvoiceProposalIssueCode.MISSING_FIELD,
                field=InvoiceProposalField.ISSUE_DATE,
            ),
        ),
        proposed_at=ACCEPTED_AT,
    )
    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            await SqlAlchemyProcessingRunRepository(session).add(
                ProcessingRun.queue(run_id=run_id, document_id=document_id, queued_at=ACCEPTED_AT)
            )
            await SqlAlchemyAiInvoiceExtractionProposalRepository(session).add(proposal)
        result = await SqlAlchemyDocumentStatusReader(database.sessions).get(document_id)
    finally:
        await database.dispose()

    assert result is not None
    assert result.current_run.ai_proposal is not None
    assert result.current_run.ai_proposal.status is InvoiceProposalStatus.PARTIAL
    assert result.current_run.ai_proposal.issues == proposal.issues
    assert result.current_run.ai_proposal.invoice_number == "INV-42"
    assert result.current_run.ai_proposal_failure is None
    assert not hasattr(result.current_run.ai_proposal, "selected_text")
    assert not hasattr(result.current_run.ai_proposal, "prompt")
    response = DocumentStatusResponse.model_validate(result).model_dump(mode="json")
    assert response["current_run"]["ai_proposal"]["issues"] == [
        {"code": "MISSING_FIELD", "field": "ISSUE_DATE"}
    ]
    assert response["current_run"]["ai_proposal_failure"] is None
    assert response["current_run"]["ai_execution"] is None
    assert "selected_text" not in response["current_run"]["ai_proposal"]
    assert "prompt" not in response["current_run"]["ai_proposal"]


@pytest.mark.anyio
async def test_returns_terminal_ai_failure_without_changing_document_status(
    migrated_postgres_url: str,
) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    document_id = uuid4()
    run_id = uuid4()
    document = Document.accept_pdf(
        document_id=document_id,
        original_filename="failure.pdf",
        size_bytes=100,
        page_count=1,
        content_sha256="c" * 64,
        storage_key="blobs/failure",
        accepted_at=ACCEPTED_AT,
    )
    failure = AiInvoiceProposalFailure(
        processing_run_id=run_id,
        provider=InvoiceModelProvider.OLLAMA,
        model_reference="qwen3:8b",
        code=InvoiceProposalGenerationFailureCode.TIMEOUT,
        failed_at=ACCEPTED_AT,
    )
    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            await SqlAlchemyProcessingRunRepository(session).add(
                ProcessingRun.queue(run_id=run_id, document_id=document_id, queued_at=ACCEPTED_AT)
            )
            await SqlAlchemyAiInvoiceProposalFailureRepository(session).add(failure)
        result = await SqlAlchemyDocumentStatusReader(database.sessions).get(document_id)
    finally:
        await database.dispose()

    assert result is not None
    assert result.current_run.ai_proposal is None
    assert result.current_run.ai_proposal_failure is not None
    assert (
        result.current_run.ai_proposal_failure.code is InvoiceProposalGenerationFailureCode.TIMEOUT
    )
    assert result.current_run.status is ProcessingRunStatus.QUEUED
    response = DocumentStatusResponse.model_validate(result).model_dump(mode="json")
    assert response["current_run"]["ai_proposal"] is None
    assert response["current_run"]["ai_proposal_failure"]["code"] == "TIMEOUT"
    assert response["current_run"]["ai_execution"] is None


@pytest.mark.anyio
@pytest.mark.parametrize("state", list(AiInvoiceProposalExecutionStatus))
async def test_returns_persisted_ai_execution_metadata(
    migrated_postgres_url: str,
    state: AiInvoiceProposalExecutionStatus,
) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    document_id, run_id = uuid4(), uuid4()
    execution = AiInvoiceProposalExecution.begin(
        processing_run_id=run_id,
        enabled=state is not AiInvoiceProposalExecutionStatus.DISABLED,
        at=ACCEPTED_AT,
    )
    terminal_at = ACCEPTED_AT + timedelta(seconds=30)
    expected = execution
    if state is AiInvoiceProposalExecutionStatus.COMPLETED:
        expected = execution.complete(at=terminal_at)
    elif state is AiInvoiceProposalExecutionStatus.FAILED:
        expected = execution.fail(at=terminal_at)
    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(
                Document.accept_pdf(
                    document_id=document_id,
                    original_filename="execution-status.pdf",
                    size_bytes=100,
                    page_count=1,
                    content_sha256=document_id.hex * 2,
                    storage_key=f"blobs/{document_id}",
                    accepted_at=ACCEPTED_AT,
                )
            )
            await SqlAlchemyProcessingRunRepository(session).add(
                ProcessingRun.queue(
                    run_id=run_id,
                    document_id=document_id,
                    queued_at=ACCEPTED_AT,
                )
            )
            repository = SqlAlchemyAiInvoiceProposalExecutionRepository(session)
            await repository.add(execution)
            if expected is not execution:
                await repository.finish(expected)
        result = await SqlAlchemyDocumentStatusReader(database.sessions).get(document_id)
    finally:
        await database.dispose()

    assert result is not None
    metadata = result.current_run.ai_execution
    assert metadata is not None
    assert metadata.status is state
    assert metadata.started_at == expected.started_at
    assert metadata.finished_at == expected.finished_at
    assert metadata.status_changed_at == expected.status_changed_at
    assert result.current_run.status is ProcessingRunStatus.QUEUED
    response = DocumentStatusResponse.model_validate(result).model_dump(mode="json")
    assert response["current_run"]["ai_execution"] == {
        "status": state.value,
        "status_changed_at": expected.status_changed_at.isoformat().replace("+00:00", "Z"),
        "started_at": (
            expected.started_at.isoformat().replace("+00:00", "Z")
            if expected.started_at is not None
            else None
        ),
        "finished_at": (
            expected.finished_at.isoformat().replace("+00:00", "Z")
            if expected.finished_at is not None
            else None
        ),
    }


@pytest.mark.anyio
async def test_returns_processing_output_metadata_without_document_text(
    migrated_postgres_url: str,
) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    document_id = uuid4()
    run_id = uuid4()
    document = Document.accept_pdf(
        document_id=document_id,
        original_filename="invoice.pdf",
        size_bytes=42_000,
        page_count=2,
        content_sha256="c" * 64,
        storage_key="blobs/sha256/cc/" + "c" * 64,
        accepted_at=ACCEPTED_AT,
    )
    run = ProcessingRun.queue(run_id=run_id, document_id=document_id, queued_at=ACCEPTED_AT)
    embedded = DocumentTextExtraction(
        processing_run_id=run_id,
        method=TextExtractionMethod.PYMUPDF,
        text="Invoice 42",
        page_count=2,
        character_count=10,
        non_whitespace_character_count=9,
        quality=EmbeddedTextQuality.OCR_RECOMMENDED,
        extracted_at=ACCEPTED_AT,
    )
    ocr = DocumentOcrExtraction(
        processing_run_id=run_id,
        method=OcrExtractionMethod.TESSERACT,
        text="Invoice 42 Total 12.50",
        page_count=2,
        character_count=22,
        non_whitespace_character_count=19,
        extracted_at=ACCEPTED_AT,
    )
    selection = DocumentTextSelection(
        processing_run_id=run_id,
        source=ProcessingTextSource.OCR,
        reason=ProcessingTextSelectionReason.OCR_HAS_MORE_TEXT,
        selected_at=ACCEPTED_AT,
    )
    classification = DocumentClassification(
        processing_run_id=run_id,
        document_type=BusinessDocumentType.INVOICE,
        reason=DocumentClassificationReason.KEYWORD_MATCHED,
        classified_at=ACCEPTED_AT,
    )
    invoice_extraction = InvoiceExtraction(
        processing_run_id=run_id,
        method=InvoiceExtractionMethod.DETERMINISTIC_RULES,
        invoice_number="INV-42",
        issue_date=date(2026, 9, 14),
        supplier_name="Acme Ltd",
        currency="EUR",
        total_amount=Decimal("12.50"),
        extracted_at=ACCEPTED_AT,
    )
    invoice_validation = InvoiceValidation(
        processing_run_id=run_id,
        decision=InvoiceValidationDecision.AUTO_APPROVE,
        issues=(),
        validated_at=ACCEPTED_AT,
    )

    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            await SqlAlchemyProcessingRunRepository(session).add(run)
            await SqlAlchemyDocumentTextExtractionRepository(session).add(embedded)
            await SqlAlchemyDocumentOcrExtractionRepository(session).add(ocr)
            await SqlAlchemyDocumentTextSelectionRepository(session).add(selection)
            await SqlAlchemyDocumentClassificationRepository(session).add(classification)
            await SqlAlchemyInvoiceExtractionRepository(session).add(invoice_extraction)
            await SqlAlchemyInvoiceValidationRepository(session).add(invoice_validation)

        result = await SqlAlchemyDocumentStatusReader(database.sessions).get(document_id)
    finally:
        await database.dispose()

    assert result is not None
    output = result.current_run.processing_output
    assert output is not None
    assert output.embedded_text is not None
    assert output.embedded_text.quality is EmbeddedTextQuality.OCR_RECOMMENDED
    assert output.ocr_text is not None
    assert output.ocr_text.character_count == 22
    assert output.selected_text is not None
    assert output.selected_text.source is ProcessingTextSource.OCR
    assert output.classification is not None
    assert output.classification.document_type is BusinessDocumentType.INVOICE
    assert output.invoice_extraction is not None
    assert output.invoice_extraction.invoice_number == "INV-42"
    assert output.invoice_extraction.total_amount == Decimal("12.50")
    assert output.invoice_validation is not None
    assert output.invoice_validation.decision is InvoiceValidationDecision.AUTO_APPROVE
    assert output.invoice_validation.issues == ()
    assert not hasattr(output.embedded_text, "text")


@pytest.mark.anyio
async def test_returns_bounded_terminal_failure_metadata(
    migrated_postgres_url: str,
) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    document_id = uuid4()
    run_id = uuid4()
    document = (
        Document.accept_pdf(
            document_id=document_id,
            original_filename="failed-invoice.pdf",
            size_bytes=42_000,
            page_count=2,
            content_sha256="e" * 64,
            storage_key="blobs/sha256/ee/" + "e" * 64,
            accepted_at=ACCEPTED_AT,
        )
        .start_processing(at=ACCEPTED_AT)
        .fail(at=ACCEPTED_AT + timedelta(seconds=2))
    )
    run = (
        ProcessingRun.queue(run_id=run_id, document_id=document_id, queued_at=ACCEPTED_AT)
        .start(at=ACCEPTED_AT + timedelta(seconds=1))
        .fail(
            at=ACCEPTED_AT + timedelta(seconds=2),
            failure=ProcessingFailure(
                stage=ProcessingStage.EMBEDDED_TEXT_EXTRACTION,
                code=ProcessingFailureCode.ACTIVITY_RETRY_EXHAUSTED,
            ),
        )
    )

    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            await SqlAlchemyProcessingRunRepository(session).add(run)

        result = await SqlAlchemyDocumentStatusReader(database.sessions).get(document_id)
    finally:
        await database.dispose()

    assert result is not None
    assert result.current_run.failure is not None
    assert result.current_run.failure.stage is ProcessingStage.EMBEDDED_TEXT_EXTRACTION
    assert result.current_run.failure.code is ProcessingFailureCode.ACTIVITY_RETRY_EXHAUSTED


@pytest.mark.anyio
async def test_returns_safe_review_resolution_metadata(
    migrated_postgres_url: str,
) -> None:
    database = create_database(
        Settings(environment="test", database_url=PostgresDsn(migrated_postgres_url))
    )
    document_id = uuid4()
    run_id = uuid4()
    document = (
        Document.accept_pdf(
            document_id=document_id,
            original_filename="review.pdf",
            size_bytes=42_000,
            page_count=2,
            content_sha256="d" * 64,
            storage_key="blobs/sha256/dd/" + "d" * 64,
            accepted_at=ACCEPTED_AT,
        )
        .start_processing(at=ACCEPTED_AT)
        .require_review(at=ACCEPTED_AT)
        .approve(at=ACCEPTED_AT)
    )
    run = (
        ProcessingRun.queue(run_id=run_id, document_id=document_id, queued_at=ACCEPTED_AT)
        .start(at=ACCEPTED_AT)
        .require_review(at=ACCEPTED_AT)
        .complete_after_review(at=ACCEPTED_AT)
    )
    resolution = ReviewResolution(
        processing_run_id=run_id,
        decision=ReviewResolutionDecision.APPROVE,
        reviewer_id="operator-42",
        review_note="Matched the supplier statement.",
        resolved_at=ACCEPTED_AT,
    )

    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            await SqlAlchemyProcessingRunRepository(session).add(run)
            await SqlAlchemyReviewResolutionRepository(session).add(resolution)
            await SqlAlchemyInvoiceReviewCorrectionRepository(session).add(
                InvoiceReviewCorrection(
                    processing_run_id=run_id,
                    corrections=(
                        InvoiceReviewFieldCorrection(
                            field=InvoiceReviewField.TOTAL_AMOUNT,
                            corrected_value=Decimal("42.50"),
                            source=InvoiceReviewCorrectionSource.AI_PROPOSAL,
                        ),
                    ),
                    corrected_at=ACCEPTED_AT,
                )
            )

        result = await SqlAlchemyDocumentStatusReader(database.sessions).get(document_id)
    finally:
        await database.dispose()

    assert result is not None
    review = result.current_run.review_resolution
    assert review is not None
    assert review.decision is ReviewResolutionDecision.APPROVE
    assert review.reviewer_id == "operator-42"
    assert review.review_note == "Matched the supplier statement."
    assert review.corrections[0].field is InvoiceReviewField.TOTAL_AMOUNT
    assert review.corrections[0].corrected_value == Decimal("42.50")
    assert review.corrections[0].source is InvoiceReviewCorrectionSource.AI_PROPOSAL
    assert review.corrections[0].corrected_at == ACCEPTED_AT
