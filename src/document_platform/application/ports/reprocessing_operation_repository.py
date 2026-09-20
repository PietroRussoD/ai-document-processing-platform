"""Persistence contract for immutable reprocessing operations."""

from typing import Protocol
from uuid import UUID

from document_platform.domain.processing import ReprocessingOperation


class ReprocessingOperationAlreadyExists(RuntimeError):
    def __init__(self, *, document_id: UUID, idempotency_key: str) -> None:
        super().__init__(
            "reprocessing operation already exists for "
            f"document {document_id} and idempotency key {idempotency_key}"
        )


class ReprocessingOperationRepository(Protocol):
    async def add(self, operation: ReprocessingOperation) -> None: ...

    async def get(
        self,
        *,
        document_id: UUID,
        idempotency_key: str,
    ) -> ReprocessingOperation | None: ...
