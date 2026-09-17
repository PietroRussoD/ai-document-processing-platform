"""Persistence contract for immutable manual review resolutions."""

from typing import Protocol
from uuid import UUID

from document_platform.domain.processing import ReviewResolution


class ReviewResolutionAlreadyExists(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"review resolution already exists: {processing_run_id}")


class ReviewResolutionRepository(Protocol):
    async def add(self, resolution: ReviewResolution) -> None: ...

    async def get(self, processing_run_id: UUID) -> ReviewResolution | None: ...
