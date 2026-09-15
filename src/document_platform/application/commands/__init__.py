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
from document_platform.application.commands.start_processing_run import (
    InvalidProcessingDocumentStart,
    InvalidProcessingRunStart,
    ProcessingRunDocumentNotFound,
    ProcessingRunNotFound,
    ProcessingRunStarted,
    StartProcessingRun,
    StartProcessingRunHandler,
)

__all__ = [
    "AcceptDocumentUpload",
    "AcceptDocumentUploadHandler",
    "ClaimWorkflowStartRequests",
    "ClaimWorkflowStartRequestsHandler",
    "DispatchWorkflowStartRequestsHandler",
    "InconsistentIdempotencyRecord",
    "InvalidStagedUpload",
    "InvalidProcessingDocumentStart",
    "InvalidProcessingRunStart",
    "InvalidWorkflowStartRequestClaim",
    "RegisterDocument",
    "RegisterDocumentHandler",
    "RegisteredDocument",
    "ProcessingRunDocumentNotFound",
    "ProcessingRunNotFound",
    "ProcessingRunStarted",
    "StartProcessingRun",
    "StartProcessingRunHandler",
    "UnsupportedDocumentMediaType",
    "WorkflowStartDispatchResult",
]
