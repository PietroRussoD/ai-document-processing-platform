"""Persistence contract for durable workflow-start requests."""

from typing import Protocol
from uuid import UUID

from document_platform.domain.processing import WorkflowStartRequest


class WorkflowStartRequestAlreadyExists(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"workflow start request already exists: {processing_run_id}")


class ConcurrentWorkflowStartRequestUpdate(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"workflow start request was concurrently updated: {processing_run_id}")


class WorkflowStartRequestRepository(Protocol):
    async def add(self, request: WorkflowStartRequest) -> None: ...

    async def get(self, processing_run_id: UUID) -> WorkflowStartRequest | None: ...

    async def update(self, request: WorkflowStartRequest) -> None: ...
