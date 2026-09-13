"""Processing-run persistence contract."""

from typing import Protocol
from uuid import UUID

from document_platform.domain.processing import ProcessingRun


class ProcessingRunAlreadyExists(RuntimeError):
    def __init__(self, run_id: UUID) -> None:
        super().__init__(f"processing run already exists: {run_id}")


class ConcurrentProcessingRunUpdate(RuntimeError):
    def __init__(self, run_id: UUID) -> None:
        super().__init__(f"processing run was concurrently updated: {run_id}")


class ProcessingRunRepository(Protocol):
    async def add(self, run: ProcessingRun) -> None: ...

    async def get(self, run_id: UUID) -> ProcessingRun | None: ...

    async def update(self, run: ProcessingRun) -> None: ...
