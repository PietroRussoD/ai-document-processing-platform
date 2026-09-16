"""SQLAlchemy implementation of the application unit of work."""

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyDocumentClassificationRepository,
    SqlAlchemyDocumentOcrExtractionRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyDocumentTextExtractionRepository,
    SqlAlchemyDocumentTextSelectionRepository,
    SqlAlchemyProcessingRunRepository,
    SqlAlchemyUploadIdempotencyRepository,
    SqlAlchemyWorkflowStartRequestRepository,
)
from document_platform.application.ports import (
    DocumentClassificationRepository,
    DocumentOcrExtractionRepository,
    DocumentRepository,
    DocumentTextExtractionRepository,
    DocumentTextSelectionRepository,
    ProcessingRunRepository,
    UploadIdempotencyRepository,
    WorkflowStartRequestRepository,
)


class SqlAlchemyUnitOfWork:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions
        self._session: AsyncSession | None = None
        self._documents: DocumentRepository | None = None
        self._document_ocr_extractions: DocumentOcrExtractionRepository | None = None
        self._document_classifications: DocumentClassificationRepository | None = None
        self._document_text_extractions: DocumentTextExtractionRepository | None = None
        self._document_text_selections: DocumentTextSelectionRepository | None = None
        self._processing_runs: ProcessingRunRepository | None = None
        self._upload_idempotency: UploadIdempotencyRepository | None = None
        self._workflow_start_requests: WorkflowStartRequestRepository | None = None

    @property
    def documents(self) -> DocumentRepository:
        if self._documents is None:
            raise RuntimeError("unit of work is not active")
        return self._documents

    @property
    def document_ocr_extractions(self) -> DocumentOcrExtractionRepository:
        if self._document_ocr_extractions is None:
            raise RuntimeError("unit of work is not active")
        return self._document_ocr_extractions

    @property
    def document_classifications(self) -> DocumentClassificationRepository:
        if self._document_classifications is None:
            raise RuntimeError("unit of work is not active")
        return self._document_classifications

    @property
    def document_text_extractions(self) -> DocumentTextExtractionRepository:
        if self._document_text_extractions is None:
            raise RuntimeError("unit of work is not active")
        return self._document_text_extractions

    @property
    def document_text_selections(self) -> DocumentTextSelectionRepository:
        if self._document_text_selections is None:
            raise RuntimeError("unit of work is not active")
        return self._document_text_selections

    @property
    def processing_runs(self) -> ProcessingRunRepository:
        if self._processing_runs is None:
            raise RuntimeError("unit of work is not active")
        return self._processing_runs

    @property
    def upload_idempotency(self) -> UploadIdempotencyRepository:
        if self._upload_idempotency is None:
            raise RuntimeError("unit of work is not active")
        return self._upload_idempotency

    @property
    def workflow_start_requests(self) -> WorkflowStartRequestRepository:
        if self._workflow_start_requests is None:
            raise RuntimeError("unit of work is not active")
        return self._workflow_start_requests

    async def __aenter__(self) -> Self:
        if self._session is not None:
            raise RuntimeError("unit of work is already active")

        self._session = self._sessions()
        self._documents = SqlAlchemyDocumentRepository(self._session)
        self._document_ocr_extractions = SqlAlchemyDocumentOcrExtractionRepository(self._session)
        self._document_classifications = SqlAlchemyDocumentClassificationRepository(self._session)
        self._document_text_extractions = SqlAlchemyDocumentTextExtractionRepository(self._session)
        self._document_text_selections = SqlAlchemyDocumentTextSelectionRepository(self._session)
        self._processing_runs = SqlAlchemyProcessingRunRepository(self._session)
        self._upload_idempotency = SqlAlchemyUploadIdempotencyRepository(self._session)
        self._workflow_start_requests = SqlAlchemyWorkflowStartRequestRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._require_session()
        try:
            await session.rollback()
        finally:
            await session.close()
            self._session = None
            self._documents = None
            self._document_ocr_extractions = None
            self._document_classifications = None
            self._document_text_extractions = None
            self._document_text_selections = None
            self._processing_runs = None
            self._upload_idempotency = None
            self._workflow_start_requests = None

    async def commit(self) -> None:
        await self._require_session().commit()

    async def rollback(self) -> None:
        await self._require_session().rollback()

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("unit of work is not active")
        return self._session
