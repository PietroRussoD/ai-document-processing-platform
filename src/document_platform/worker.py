"""Standalone Temporal worker for document-processing workflows."""

import asyncio
import logging
from datetime import UTC, datetime

from temporalio.client import Client
from temporalio.worker import Worker

from document_platform.adapters.inbound.temporal import (
    ClassifyDocumentActivity,
    CompleteProcessingRunActivity,
    ExtractDocumentTextActivity,
    ExtractOcrTextActivity,
    SelectProcessingTextActivity,
    StartProcessingRunActivity,
)
from document_platform.adapters.outbound.filesystem import LocalBlobStore
from document_platform.adapters.outbound.ocr import TesseractPdfOcrExtractor
from document_platform.adapters.outbound.pdf import PyMuPdfTextExtractor
from document_platform.adapters.outbound.postgresql import SqlAlchemyUnitOfWork
from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.application.commands import (
    ClassifyDocumentHandler,
    CompleteProcessingRunHandler,
    ExtractDocumentTextHandler,
    ExtractOcrTextHandler,
    SelectProcessingTextHandler,
    StartProcessingRunHandler,
)
from document_platform.domain.processing import (
    DocumentClassificationPolicy,
    EmbeddedTextQualityPolicy,
    ProcessingTextSelectionPolicy,
)
from document_platform.settings import Settings
from document_platform.workflows import ProcessBusinessDocumentWorkflow


async def run_worker(settings: Settings) -> None:
    database = create_database(settings)
    try:
        client = await Client.connect(
            settings.temporal_target_host,
            namespace=settings.temporal_namespace,
        )

        def unit_of_work_factory() -> SqlAlchemyUnitOfWork:
            return SqlAlchemyUnitOfWork(database.sessions)

        start_activity = StartProcessingRunActivity(
            StartProcessingRunHandler(
                unit_of_work_factory=unit_of_work_factory,
                clock=lambda: datetime.now(UTC),
            )
        )
        extract_activity = ExtractDocumentTextActivity(
            ExtractDocumentTextHandler(
                unit_of_work_factory=unit_of_work_factory,
                blob_store=LocalBlobStore(
                    root=settings.storage_root,
                    max_bytes=settings.max_document_bytes,
                ),
                pdf_text_extractor=PyMuPdfTextExtractor(
                    max_pages=settings.max_document_pages,
                    max_characters=settings.max_extracted_text_characters,
                ),
                embedded_text_quality_policy=EmbeddedTextQualityPolicy(
                    settings.minimum_embedded_text_characters
                ),
                clock=lambda: datetime.now(UTC),
            )
        )
        ocr_activity = ExtractOcrTextActivity(
            ExtractOcrTextHandler(
                unit_of_work_factory=unit_of_work_factory,
                blob_store=LocalBlobStore(
                    root=settings.storage_root,
                    max_bytes=settings.max_document_bytes,
                ),
                pdf_ocr_extractor=TesseractPdfOcrExtractor(
                    command=settings.tesseract_command,
                    language=settings.tesseract_language,
                    max_pages=settings.max_document_pages,
                    max_characters=settings.max_extracted_text_characters,
                    raster_dpi=settings.tesseract_raster_dpi,
                    page_timeout_seconds=settings.tesseract_page_timeout_seconds,
                ),
                clock=lambda: datetime.now(UTC),
            )
        )
        selection_activity = SelectProcessingTextActivity(
            SelectProcessingTextHandler(
                unit_of_work_factory=unit_of_work_factory,
                selection_policy=ProcessingTextSelectionPolicy(),
                clock=lambda: datetime.now(UTC),
            )
        )
        classification_activity = ClassifyDocumentActivity(
            ClassifyDocumentHandler(
                unit_of_work_factory=unit_of_work_factory,
                classification_policy=DocumentClassificationPolicy(),
                clock=lambda: datetime.now(UTC),
            )
        )
        completion_activity = CompleteProcessingRunActivity(
            CompleteProcessingRunHandler(
                unit_of_work_factory=unit_of_work_factory,
                clock=lambda: datetime.now(UTC),
            )
        )
        worker = Worker(
            client,
            task_queue=settings.temporal_task_queue,
            workflows=[ProcessBusinessDocumentWorkflow],
            activities=[
                start_activity.start_processing_run,
                extract_activity.extract_document_text,
                ocr_activity.extract_ocr_text,
                selection_activity.select_processing_text,
                classification_activity.classify_document,
                completion_activity.complete_processing_run,
            ],
        )
        await worker.run()
    finally:
        await database.dispose()


def main() -> None:
    settings = Settings()
    logging.basicConfig(level=settings.log_level)
    try:
        asyncio.run(run_worker(settings))
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
