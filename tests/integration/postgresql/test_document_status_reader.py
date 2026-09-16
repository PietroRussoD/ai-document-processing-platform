"""PostgreSQL document-status read-model integration tests."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import PostgresDsn

from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.adapters.outbound.postgresql.queries import SqlAlchemyDocumentStatusReader
from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentClassificationRepository,
    SqlAlchemyDocumentOcrExtractionRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyDocumentTextExtractionRepository,
    SqlAlchemyDocumentTextSelectionRepository,
    SqlAlchemyProcessingRunRepository,
)
from document_platform.domain.documents import Document
from document_platform.domain.processing import (
    BusinessDocumentType,
    DocumentClassification,
    DocumentClassificationReason,
    DocumentOcrExtraction,
    DocumentTextExtraction,
    DocumentTextSelection,
    EmbeddedTextQuality,
    OcrExtractionMethod,
    ProcessingRun,
    ProcessingTextSelectionReason,
    ProcessingTextSource,
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
    first_run = ProcessingRun.queue(
        run_id=first_run_id,
        document_id=document_id,
        queued_at=ACCEPTED_AT,
    )
    latest_run = ProcessingRun.queue(
        run_id=latest_run_id,
        document_id=document_id,
        queued_at=ACCEPTED_AT + timedelta(minutes=5),
    )

    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            runs = SqlAlchemyProcessingRunRepository(session)
            await runs.add(first_run)
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
    assert result.current_run.queued_at == latest_run.queued_at
    assert result.current_run.processing_output is None
    assert missing is None


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

    try:
        async with database.sessions.begin() as session:
            await SqlAlchemyDocumentRepository(session).add(document)
            await SqlAlchemyProcessingRunRepository(session).add(run)
            await SqlAlchemyDocumentTextExtractionRepository(session).add(embedded)
            await SqlAlchemyDocumentOcrExtractionRepository(session).add(ocr)
            await SqlAlchemyDocumentTextSelectionRepository(session).add(selection)
            await SqlAlchemyDocumentClassificationRepository(session).add(classification)

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
    assert not hasattr(output.embedded_text, "text")
