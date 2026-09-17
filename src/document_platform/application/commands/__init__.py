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
from document_platform.application.commands.classify_document import (
    ClassificationRequiresSelectedText,
    ClassificationRequiresTextSelection,
    ClassifyDocument,
    ClassifyDocumentHandler,
    DocumentClassified,
)
from document_platform.application.commands.complete_processing_run import (
    CompleteProcessingRun,
    CompleteProcessingRunHandler,
    InvalidProcessingRunCompletion,
    ProcessingRunCompleted,
    ProcessingRunCompletionNotFound,
)
from document_platform.application.commands.dispatch_workflow_start_requests import (
    DispatchWorkflowStartRequestsHandler,
    WorkflowStartDispatchResult,
)
from document_platform.application.commands.extract_document_text import (
    DocumentTextExtracted,
    ExtractDocumentText,
    ExtractDocumentTextHandler,
    InvalidTextExtractionRun,
    TextExtractionDocumentNotFound,
    TextExtractionRunNotFound,
)
from document_platform.application.commands.extract_invoice import (
    ExtractInvoice,
    ExtractInvoiceHandler,
    InvoiceExtracted,
    InvoiceExtractionNotApplicable,
    InvoiceExtractionRequiresClassification,
    InvoiceExtractionRequiresSelectedText,
    InvoiceExtractionRequiresTextSelection,
)
from document_platform.application.commands.extract_ocr_text import (
    ExtractOcrText,
    ExtractOcrTextHandler,
    OcrTextExtractionResult,
)
from document_platform.application.commands.register_document import (
    InconsistentIdempotencyRecord,
    RegisterDocument,
    RegisterDocumentHandler,
    RegisteredDocument,
)
from document_platform.application.commands.select_processing_text import (
    ProcessingTextSelected,
    SelectProcessingText,
    SelectProcessingTextHandler,
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
from document_platform.application.commands.validate_invoice import (
    InvoiceValidated,
    InvoiceValidationRequiresExtraction,
    ValidateInvoice,
    ValidateInvoiceHandler,
)

__all__ = [
    "AcceptDocumentUpload",
    "AcceptDocumentUploadHandler",
    "ClaimWorkflowStartRequests",
    "ClaimWorkflowStartRequestsHandler",
    "ClassifyDocument",
    "ClassifyDocumentHandler",
    "ClassificationRequiresSelectedText",
    "ClassificationRequiresTextSelection",
    "CompleteProcessingRun",
    "CompleteProcessingRunHandler",
    "DispatchWorkflowStartRequestsHandler",
    "DocumentTextExtracted",
    "DocumentClassified",
    "ExtractDocumentText",
    "ExtractDocumentTextHandler",
    "ExtractInvoice",
    "ExtractInvoiceHandler",
    "ExtractOcrText",
    "ExtractOcrTextHandler",
    "InconsistentIdempotencyRecord",
    "InvalidStagedUpload",
    "InvalidTextExtractionRun",
    "InvoiceExtracted",
    "InvoiceExtractionNotApplicable",
    "InvoiceExtractionRequiresClassification",
    "InvoiceExtractionRequiresSelectedText",
    "InvoiceExtractionRequiresTextSelection",
    "InvoiceValidated",
    "InvoiceValidationRequiresExtraction",
    "OcrTextExtractionResult",
    "InvalidProcessingDocumentStart",
    "InvalidProcessingRunStart",
    "InvalidProcessingRunCompletion",
    "InvalidWorkflowStartRequestClaim",
    "RegisterDocument",
    "RegisterDocumentHandler",
    "RegisteredDocument",
    "ProcessingRunDocumentNotFound",
    "ProcessingRunCompleted",
    "ProcessingRunCompletionNotFound",
    "ProcessingRunNotFound",
    "ProcessingRunStarted",
    "ProcessingTextSelected",
    "StartProcessingRun",
    "StartProcessingRunHandler",
    "SelectProcessingText",
    "SelectProcessingTextHandler",
    "TextExtractionDocumentNotFound",
    "TextExtractionRunNotFound",
    "UnsupportedDocumentMediaType",
    "ValidateInvoice",
    "ValidateInvoiceHandler",
    "WorkflowStartDispatchResult",
]
