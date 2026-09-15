"""Boundary for starting durable processing workflows."""

from typing import Protocol
from uuid import UUID

PROCESS_BUSINESS_DOCUMENT_WORKFLOW = "process-business-document"


class WorkflowStarter(Protocol):
    async def start(
        self,
        *,
        workflow_id: str,
        processing_run_id: UUID,
    ) -> None: ...
