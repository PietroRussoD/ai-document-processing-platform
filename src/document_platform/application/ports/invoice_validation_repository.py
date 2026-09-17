"""Persistence contract for immutable invoice validations."""

from typing import Protocol
from uuid import UUID

from document_platform.domain.processing import InvoiceValidation


class InvoiceValidationAlreadyExists(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"invoice validation already exists: {processing_run_id}")


class InvoiceValidationRepository(Protocol):
    async def add(self, validation: InvoiceValidation) -> None: ...

    async def get(self, processing_run_id: UUID) -> InvoiceValidation | None: ...
