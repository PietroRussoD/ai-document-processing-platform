"""Application composition root."""

from importlib.metadata import version

from fastapi import FastAPI

from document_platform.adapters.inbound.http.health import router as health_router
from document_platform.settings import Settings

PACKAGE_NAME = "ai-document-processing-platform"


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or Settings()
    application_version = version(PACKAGE_NAME)

    application = FastAPI(
        title="AI Document Processing Platform",
        version=application_version,
        debug=active_settings.environment == "local",
    )
    application.state.settings = active_settings
    application.include_router(health_router)
    return application


app = create_app()
