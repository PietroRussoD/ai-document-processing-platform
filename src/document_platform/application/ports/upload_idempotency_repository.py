"""Upload idempotency persistence contract."""

from typing import Protocol

from document_platform.application.upload_idempotency import (
    IdempotencyKey,
    UploadIdempotencyRecord,
)


class UploadIdempotencyRecordAlreadyExists(RuntimeError):
    def __init__(self, key: IdempotencyKey) -> None:
        super().__init__(f"upload idempotency record already exists: {key.value}")


class UploadIdempotencyRepository(Protocol):
    async def add(self, record: UploadIdempotencyRecord) -> None: ...

    async def get(self, key: IdempotencyKey) -> UploadIdempotencyRecord | None: ...
