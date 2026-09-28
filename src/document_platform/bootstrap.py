"""Application composition root."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from importlib.metadata import version
from uuid import uuid4

from fastapi import FastAPI

from document_platform.adapters.inbound.http.documents import router as documents_router
from document_platform.adapters.inbound.http.health import router as health_router
from document_platform.adapters.inbound.http.observability import (
    HttpMetrics,
    observe_request,
)
from document_platform.adapters.inbound.http.observability import (
    router as observability_router,
)
from document_platform.adapters.inbound.http.problems import install_problem_handlers
from document_platform.adapters.inbound.http.request_correlation import (
    correlate_request,
    current_correlation_id,
)
from document_platform.adapters.outbound.filesystem import LocalBlobStore
from document_platform.adapters.outbound.pdf import PyMuPdfInspector
from document_platform.adapters.outbound.postgresql import SqlAlchemyUnitOfWork
from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.adapters.outbound.postgresql.queries import (
    SqlAlchemyDocumentSourceReader,
    SqlAlchemyDocumentStatusReader,
    SqlAlchemyProcessingRunMetricsReader,
)
from document_platform.application.commands import (
    AcceptDocumentUploadHandler,
    RegisterDocumentHandler,
    RequestDocumentReprocessingHandler,
    ResolveDocumentReviewHandler,
)
from document_platform.application.ports import ProcessingRunMetricsReader
from document_platform.application.queries import (
    GetDocumentSourceHandler,
    GetDocumentStatusHandler,
    ListDocumentWorkQueueHandler,
)
from document_platform.logging_configuration import configure_json_logging
from document_platform.settings import Settings

PACKAGE_NAME = "ai-document-processing-platform"


def create_app(
    settings: Settings | None = None,
    processing_run_metrics_reader: ProcessingRunMetricsReader | None = None,
) -> FastAPI:
    active_settings = settings or Settings()
    application_version = version(PACKAGE_NAME)
    database = create_database(active_settings)
    register_document = RegisterDocumentHandler(
        unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(database.sessions),
        clock=lambda: datetime.now(UTC),
        id_generator=uuid4,
    )
    blob_store = LocalBlobStore(
        active_settings.storage_root,
        max_bytes=active_settings.max_document_bytes,
    )
    accept_document_upload = AcceptDocumentUploadHandler(
        pdf_inspector=PyMuPdfInspector(active_settings.max_document_pages),
        blob_store=blob_store,
        register_document=register_document,
        max_bytes=active_settings.max_document_bytes,
    )
    document_status_reader = SqlAlchemyDocumentStatusReader(database.sessions)
    get_document_status = GetDocumentStatusHandler(document_status_reader)
    get_document_source = GetDocumentSourceHandler(
        reader=SqlAlchemyDocumentSourceReader(database.sessions),
        blob_store=blob_store,
    )
    list_document_work_queue = ListDocumentWorkQueueHandler(document_status_reader)
    resolve_document_review = ResolveDocumentReviewHandler(
        unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(database.sessions),
        clock=lambda: datetime.now(UTC),
    )
    request_document_reprocessing = RequestDocumentReprocessingHandler(
        unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(database.sessions),
        clock=lambda: datetime.now(UTC),
        id_generator=uuid4,
    )

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncGenerator[None]:
        configure_json_logging(
            level=active_settings.log_level,
            component="api",
            correlation_id_provider=current_correlation_id,
        )
        yield
        await database.dispose()

    application = FastAPI(
        title="AI Document Processing Platform",
        version=application_version,
        debug=active_settings.environment == "local",
        lifespan=lifespan,
    )
    application.state.settings = active_settings
    application.state.database = database
    application.state.accept_document_upload = accept_document_upload
    application.state.get_document_status = get_document_status
    application.state.get_document_source = get_document_source
    application.state.list_document_work_queue = list_document_work_queue
    application.state.resolve_document_review = resolve_document_review
    application.state.request_document_reprocessing = request_document_reprocessing
    application.state.http_metrics = HttpMetrics(application_version=application_version)
    application.state.processing_run_metrics_reader = (
        processing_run_metrics_reader or SqlAlchemyProcessingRunMetricsReader(database.sessions)
    )
    application.middleware("http")(observe_request)
    application.middleware("http")(correlate_request)
    install_problem_handlers(application)
    application.include_router(health_router)
    application.include_router(observability_router)
    application.include_router(documents_router)
    return application


app = create_app()
