"""Application write use cases."""

from document_platform.application.commands.accept_document_upload import (
    AcceptDocumentUpload,
    AcceptDocumentUploadHandler,
    InvalidStagedUpload,
    UnsupportedDocumentMediaType,
)
from document_platform.application.commands.claim_workflow_start_requests import (
    ClaimWorkflowStartRequests,
    ClaimWorkflowStartRequestsHandler,
    InvalidWorkflowStartRequestClaim,
)
from document_platform.application.commands.dispatch_workflow_start_requests import (
    DispatchWorkflowStartRequestsHandler,
    WorkflowStartDispatchResult,
)
from document_platform.application.commands.register_document import (
    InconsistentIdempotencyRecord,
    RegisterDocument,
    RegisterDocumentHandler,
    RegisteredDocument,
)

__all__ = [
    "AcceptDocumentUpload",
    "AcceptDocumentUploadHandler",
    "ClaimWorkflowStartRequests",
    "ClaimWorkflowStartRequestsHandler",
    "DispatchWorkflowStartRequestsHandler",
    "InconsistentIdempotencyRecord",
    "InvalidStagedUpload",
    "InvalidWorkflowStartRequestClaim",
    "RegisterDocument",
    "RegisterDocumentHandler",
    "RegisteredDocument",
    "UnsupportedDocumentMediaType",
    "WorkflowStartDispatchResult",
]
