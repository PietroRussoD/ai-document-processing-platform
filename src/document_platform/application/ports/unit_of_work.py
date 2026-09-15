"""Atomic application transaction contract."""

from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self

from document_platform.application.ports.document_repository import DocumentRepository
from document_platform.application.ports.document_text_extraction_repository import (
    DocumentTextExtractionRepository,
)
from document_platform.application.ports.processing_run_repository import ProcessingRunRepository
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
    def processing_runs(self) -> ProcessingRunRepository: ...

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
