"""SQLAlchemy implementation of the application unit of work."""

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from document_platform.adapters.outbound.postgresql.repositories import (
    SqlAlchemyAiInvoiceExtractionProposalRepository,
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
    SqlAlchemyReprocessingOperationRepository,
    SqlAlchemyReviewResolutionRepository,
    SqlAlchemyUploadIdempotencyRepository,
    SqlAlchemyWorkflowStartRequestRepository,
)
from document_platform.application.ports import (
    DocumentClassificationRepository,
    DocumentOcrExtractionRepository,
    DocumentRepository,
    DocumentTextExtractionRepository,
    DocumentTextSelectionRepository,
    InvoiceExtractionRepository,
    InvoiceProposalFailureRepository,
    InvoiceProposalRepository,
    InvoiceReviewCorrectionRepository,
    InvoiceValidationRepository,
    ProcessingRunRepository,
    ReprocessingOperationRepository,
    ReviewResolutionRepository,
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
        self._invoice_extractions: InvoiceExtractionRepository | None = None
        self._invoice_proposals: InvoiceProposalRepository | None = None
        self._invoice_proposal_failures: InvoiceProposalFailureRepository | None = None
        self._invoice_review_corrections: InvoiceReviewCorrectionRepository | None = None
        self._invoice_validations: InvoiceValidationRepository | None = None
        self._processing_runs: ProcessingRunRepository | None = None
        self._reprocessing_operations: ReprocessingOperationRepository | None = None
        self._review_resolutions: ReviewResolutionRepository | None = None
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
    def invoice_extractions(self) -> InvoiceExtractionRepository:
        if self._invoice_extractions is None:
            raise RuntimeError("unit of work is not active")
        return self._invoice_extractions

    @property
    def invoice_proposals(self) -> InvoiceProposalRepository:
        if self._invoice_proposals is None:
            raise RuntimeError("unit of work is not active")
        return self._invoice_proposals

    @property
    def invoice_proposal_failures(self) -> InvoiceProposalFailureRepository:
        if self._invoice_proposal_failures is None:
            raise RuntimeError("unit of work is not active")
        return self._invoice_proposal_failures

    @property
    def invoice_review_corrections(self) -> InvoiceReviewCorrectionRepository:
        if self._invoice_review_corrections is None:
            raise RuntimeError("unit of work is not active")
        return self._invoice_review_corrections

    @property
    def invoice_validations(self) -> InvoiceValidationRepository:
        if self._invoice_validations is None:
            raise RuntimeError("unit of work is not active")
        return self._invoice_validations

    @property
    def processing_runs(self) -> ProcessingRunRepository:
        if self._processing_runs is None:
            raise RuntimeError("unit of work is not active")
        return self._processing_runs

    @property
    def reprocessing_operations(self) -> ReprocessingOperationRepository:
        if self._reprocessing_operations is None:
            raise RuntimeError("unit of work is not active")
        return self._reprocessing_operations

    @property
    def review_resolutions(self) -> ReviewResolutionRepository:
        if self._review_resolutions is None:
            raise RuntimeError("unit of work is not active")
        return self._review_resolutions

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
        self._invoice_extractions = SqlAlchemyInvoiceExtractionRepository(self._session)
        self._invoice_proposals = SqlAlchemyAiInvoiceExtractionProposalRepository(self._session)
        self._invoice_proposal_failures = SqlAlchemyAiInvoiceProposalFailureRepository(
            self._session
        )
        self._invoice_review_corrections = SqlAlchemyInvoiceReviewCorrectionRepository(
            self._session
        )
        self._invoice_validations = SqlAlchemyInvoiceValidationRepository(self._session)
        self._processing_runs = SqlAlchemyProcessingRunRepository(self._session)
        self._reprocessing_operations = SqlAlchemyReprocessingOperationRepository(self._session)
        self._review_resolutions = SqlAlchemyReviewResolutionRepository(self._session)
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
            self._invoice_extractions = None
            self._invoice_proposals = None
            self._invoice_proposal_failures = None
            self._invoice_review_corrections = None
            self._invoice_validations = None
            self._processing_runs = None
            self._reprocessing_operations = None
            self._review_resolutions = None
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
