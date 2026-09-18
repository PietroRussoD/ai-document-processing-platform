"""Persistence contract for immutable operator invoice corrections."""

from typing import Protocol
from uuid import UUID

from document_platform.domain.processing import InvoiceReviewCorrection


class InvoiceReviewCorrectionAlreadyExists(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"invoice review correction already exists: {processing_run_id}")


class InvoiceReviewCorrectionRepository(Protocol):
    async def add(self, correction: InvoiceReviewCorrection) -> None: ...

    async def get(self, processing_run_id: UUID) -> InvoiceReviewCorrection | None: ...
