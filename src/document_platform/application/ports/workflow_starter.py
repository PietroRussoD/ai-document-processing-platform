"""Boundary for starting durable processing workflows."""

from typing import Protocol
from uuid import UUID

from document_platform.application.temporal_contracts import PROCESS_BUSINESS_DOCUMENT_WORKFLOW

__all__ = ["PROCESS_BUSINESS_DOCUMENT_WORKFLOW", "WorkflowStarter"]


class WorkflowStarter(Protocol):
    async def start(
        self,
        *,
        workflow_id: str,
        processing_run_id: UUID,
    ) -> None: ...
