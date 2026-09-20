"""Atomic application transaction contract."""

from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self

from document_platform.application.ports.document_classification_repository import (
    DocumentClassificationRepository,
)
from document_platform.application.ports.document_ocr_extraction_repository import (
    DocumentOcrExtractionRepository,
)
from document_platform.application.ports.document_repository import DocumentRepository
from document_platform.application.ports.document_text_extraction_repository import (
    DocumentTextExtractionRepository,
)
from document_platform.application.ports.document_text_selection_repository import (
    DocumentTextSelectionRepository,
)
from document_platform.application.ports.invoice_extraction_repository import (
    InvoiceExtractionRepository,
)
from document_platform.application.ports.invoice_review_correction_repository import (
    InvoiceReviewCorrectionRepository,
)
from document_platform.application.ports.invoice_validation_repository import (
    InvoiceValidationRepository,
)
from document_platform.application.ports.processing_run_repository import ProcessingRunRepository
from document_platform.application.ports.reprocessing_operation_repository import (
    ReprocessingOperationRepository,
)
from document_platform.application.ports.review_resolution_repository import (
    ReviewResolutionRepository,
)
from document_platform.application.ports.upload_idempotency_repository import (
    UploadIdempotencyRepository,
)
from document_platform.application.ports.workflow_start_request_repository import (
    WorkflowStartRequestRepository,
)


class UnitOfWork(Protocol):
    @property
    def documents(self) -> DocumentRepository: ...

    @property
    def document_text_extractions(self) -> DocumentTextExtractionRepository: ...

    @property
    def document_text_selections(self) -> DocumentTextSelectionRepository: ...

    @property
    def document_ocr_extractions(self) -> DocumentOcrExtractionRepository: ...

    @property
    def document_classifications(self) -> DocumentClassificationRepository: ...

    @property
    def invoice_extractions(self) -> InvoiceExtractionRepository: ...

    @property
    def invoice_review_corrections(self) -> InvoiceReviewCorrectionRepository: ...

    @property
    def invoice_validations(self) -> InvoiceValidationRepository: ...

    @property
    def review_resolutions(self) -> ReviewResolutionRepository: ...

    @property
    def processing_runs(self) -> ProcessingRunRepository: ...

    @property
    def reprocessing_operations(self) -> ReprocessingOperationRepository: ...

    @property
    def upload_idempotency(self) -> UploadIdempotencyRepository: ...

    @property
    def workflow_start_requests(self) -> WorkflowStartRequestRepository: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


type UnitOfWorkFactory = Callable[[], UnitOfWork]
