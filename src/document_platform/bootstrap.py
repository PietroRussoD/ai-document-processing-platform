"""Application composition root."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from importlib.metadata import version
from uuid import uuid4

from fastapi import FastAPI

from document_platform.adapters.inbound.http.documents import router as documents_router
from document_platform.adapters.inbound.http.health import router as health_router
from document_platform.adapters.inbound.http.problems import install_problem_handlers
from document_platform.adapters.outbound.filesystem import LocalBlobStore
from document_platform.adapters.outbound.pdf import PyMuPdfInspector
from document_platform.adapters.outbound.postgresql import SqlAlchemyUnitOfWork
from document_platform.adapters.outbound.postgresql.database import create_database
from document_platform.adapters.outbound.postgresql.queries import SqlAlchemyDocumentStatusReader
from document_platform.application.commands import (
    AcceptDocumentUploadHandler,
    RegisterDocumentHandler,
)
from document_platform.application.queries import GetDocumentStatusHandler
from document_platform.settings import Settings

PACKAGE_NAME = "ai-document-processing-platform"


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or Settings()
    application_version = version(PACKAGE_NAME)
    database = create_database(active_settings)
    register_document = RegisterDocumentHandler(
        unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(database.sessions),
        clock=lambda: datetime.now(UTC),
        id_generator=uuid4,
    )
    accept_document_upload = AcceptDocumentUploadHandler(
        pdf_inspector=PyMuPdfInspector(active_settings.max_document_pages),
        blob_store=LocalBlobStore(
            active_settings.storage_root,
            max_bytes=active_settings.max_document_bytes,
        ),
        register_document=register_document,
        max_bytes=active_settings.max_document_bytes,
    )
    get_document_status = GetDocumentStatusHandler(
        SqlAlchemyDocumentStatusReader(database.sessions)
    )

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncGenerator[None]:
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
    install_problem_handlers(application)
    application.include_router(health_router)
    application.include_router(documents_router)
    return application


app = create_app()
