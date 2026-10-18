"""Standalone Temporal worker for document-processing workflows."""

import asyncio
from datetime import UTC, datetime

from temporalio.client import Client
from temporalio.worker import Worker

from document_platform.adapters.inbound.temporal import (
    ApplyInvoiceValidationActivity,
    ClassifyDocumentActivity,
    CompleteProcessingRunActivity,
    ExtractDocumentTextActivity,
    ExtractInvoiceActivity,
    ExtractOcrTextActivity,
    ProposeInvoiceFieldsActivity,
    RecordInvoiceProposalFailureActivity,
    RecordProcessingRunFailureActivity,
    SelectProcessingTextActivity,
    StartProcessingRunActivity,
    ValidateInvoiceActivity,
)
from document_platform.adapters.outbound.filesystem import LocalBlobStore
from document_platform.adapters.outbound.kubernetes import (
    KubernetesParserJobController,
    KubernetesParserJobSettings,
    KubernetesParserRuntimeConnection,
    KubernetesParserRuntimeSettings,
    KubernetesPdfOcrExtractor,
    KubernetesPdfTextExtractor,
)
from document_platform.adapters.outbound.ollama import (
    OllamaInvoiceProposalAdapter,
    OllamaInvoiceProposalSettings,
)
from document_platform.adapters.outbound.pdf import LocalFaultInjectingPdfTextExtractor
from document_platform.adapters.outbound.postgresql import SqlAlchemyUnitOfWork
from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.application.commands import (
    ApplyInvoiceValidationHandler,
    ClassifyDocumentHandler,
    CompleteProcessingRunHandler,
    ExtractDocumentTextHandler,
    ExtractInvoiceHandler,
    ExtractOcrTextHandler,
    ProposeInvoiceFieldsHandler,
    RecordInvoiceProposalFailureHandler,
    RecordProcessingRunFailureHandler,
    SelectProcessingTextHandler,
    StartProcessingRunHandler,
    ValidateInvoiceHandler,
)
from document_platform.application.ports import PdfTextExtractor
from document_platform.domain.processing import (
    DeterministicInvoiceExtractionPolicy,
    DocumentClassificationPolicy,
    EmbeddedTextQualityPolicy,
    InvoiceModelProvider,
    InvoiceValidationPolicy,
    ProcessingStage,
    ProcessingTextSelectionPolicy,
)
from document_platform.logging_configuration import configure_json_logging
from document_platform.settings import Settings
from document_platform.workflows import ProcessBusinessDocumentWorkflow


async def run_worker(settings: Settings) -> None:
    parser_connection, parser_controller = _create_parser_runtime(settings)
    await asyncio.to_thread(parser_connection.verify_connection)
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
        pdf_text_extractor: PdfTextExtractor = KubernetesPdfTextExtractor(
            controller=parser_controller,
            max_pages=settings.max_document_pages,
            max_characters=settings.max_extracted_text_characters,
        )
        if settings.fault_injection_stage is ProcessingStage.EMBEDDED_TEXT_EXTRACTION:
            pdf_text_extractor = LocalFaultInjectingPdfTextExtractor()

        extract_activity = ExtractDocumentTextActivity(
            ExtractDocumentTextHandler(
                unit_of_work_factory=unit_of_work_factory,
                blob_store=LocalBlobStore(
                    root=settings.storage_root,
                    max_bytes=settings.max_document_bytes,
                ),
                pdf_text_extractor=pdf_text_extractor,
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
                pdf_ocr_extractor=KubernetesPdfOcrExtractor(
                    controller=parser_controller,
                    max_pages=settings.max_document_pages,
                    max_characters=settings.max_extracted_text_characters,
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
        invoice_extraction_activity = ExtractInvoiceActivity(
            ExtractInvoiceHandler(
                unit_of_work_factory=unit_of_work_factory,
                extraction_policy=DeterministicInvoiceExtractionPolicy(),
                clock=lambda: datetime.now(UTC),
            )
        )
        invoice_proposal_activity = ProposeInvoiceFieldsActivity(
            ProposeInvoiceFieldsHandler(
                unit_of_work_factory=unit_of_work_factory,
                clock=lambda: datetime.now(UTC),
                proposal_generator=OllamaInvoiceProposalAdapter(
                    settings=OllamaInvoiceProposalSettings(
                        base_url=settings.ollama_base_url,
                        model_reference=settings.ollama_model_reference,
                        model_digest=settings.ollama_model_digest,
                        timeout_seconds=settings.ollama_timeout_seconds,
                    )
                ),
            ),
            enabled=settings.ollama_enabled,
            max_concurrent_requests=settings.ollama_max_concurrent_requests,
        )
        invoice_proposal_failure_activity = RecordInvoiceProposalFailureActivity(
            RecordInvoiceProposalFailureHandler(
                unit_of_work_factory=unit_of_work_factory,
                clock=lambda: datetime.now(UTC),
            ),
            provider=InvoiceModelProvider.OLLAMA,
            model_reference=settings.ollama_model_reference,
        )
        invoice_validation_activity = ValidateInvoiceActivity(
            ValidateInvoiceHandler(
                unit_of_work_factory=unit_of_work_factory,
                validation_policy=InvoiceValidationPolicy(),
                clock=lambda: datetime.now(UTC),
            )
        )
        invoice_validation_application_activity = ApplyInvoiceValidationActivity(
            ApplyInvoiceValidationHandler(
                unit_of_work_factory=unit_of_work_factory,
                clock=lambda: datetime.now(UTC),
            )
        )
        completion_activity = CompleteProcessingRunActivity(
            CompleteProcessingRunHandler(
                unit_of_work_factory=unit_of_work_factory,
                clock=lambda: datetime.now(UTC),
            )
        )
        failure_activity = RecordProcessingRunFailureActivity(
            RecordProcessingRunFailureHandler(
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
                invoice_extraction_activity.extract_invoice,
                invoice_proposal_activity.propose_invoice_fields,
                invoice_proposal_failure_activity.record_invoice_proposal_failure,
                invoice_validation_activity.validate_invoice,
                invoice_validation_application_activity.apply_invoice_validation,
                completion_activity.complete_processing_run,
                failure_activity.record_processing_run_failure,
            ],
        )
        await worker.run()
    finally:
        await database.dispose()


def _create_parser_runtime(
    settings: Settings,
) -> tuple[KubernetesParserRuntimeConnection, KubernetesParserJobController]:
    endpoint = settings.parser_kubernetes_endpoint
    namespace = settings.parser_kubernetes_namespace
    ca_file = settings.parser_kubernetes_ca_file
    token_file = settings.parser_kubernetes_token_file
    image = settings.parser_job_image
    required = {
        "parser_kubernetes_endpoint": endpoint,
        "parser_kubernetes_namespace": namespace,
        "parser_kubernetes_ca_file": ca_file,
        "parser_kubernetes_token_file": token_file,
        "parser_job_image": image,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise ValueError(
            "isolated parser runtime configuration is required; missing " + ", ".join(missing)
        )
    assert endpoint is not None
    assert namespace is not None
    assert ca_file is not None
    assert token_file is not None
    assert image is not None

    connection = KubernetesParserRuntimeConnection(
        KubernetesParserRuntimeSettings(
            endpoint=endpoint,
            namespace=namespace,
            ca_file=ca_file,
            token_file=token_file,
        )
    )
    controller = KubernetesParserJobController(
        connection=connection,
        settings=KubernetesParserJobSettings(
            image=image,
            max_input_bytes=settings.max_document_bytes,
            max_output_bytes=settings.max_extracted_text_characters * 6 + 2_048,
            cpu_request="250m",
            cpu_limit="1",
            memory_request="512Mi",
            memory_limit="1Gi",
            ephemeral_storage_request="64Mi",
            ephemeral_storage_limit="128Mi",
            scratch_limit="64Mi",
            active_deadline_seconds=120,
            ttl_seconds_after_finished=60,
            max_concurrent_jobs=2,
            startup_timeout_seconds=20,
            execution_timeout_seconds=90,
            cleanup_timeout_seconds=10,
            max_pages=settings.max_document_pages,
            max_characters=settings.max_extracted_text_characters,
            tesseract_language=settings.tesseract_language,
            tesseract_raster_dpi=settings.tesseract_raster_dpi,
            tesseract_max_page_pixels=settings.tesseract_max_page_pixels,
            tesseract_page_timeout_seconds=settings.tesseract_page_timeout_seconds,
        ),
    )
    return connection, controller


def main() -> None:
    settings = Settings()
    configure_json_logging(level=settings.log_level, component="worker")
    try:
        asyncio.run(run_worker(settings))
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
