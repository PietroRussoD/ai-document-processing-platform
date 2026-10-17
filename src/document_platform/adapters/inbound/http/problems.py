"""RFC 9457 responses for expected request failures."""

from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from document_platform.adapters.inbound.http.review_authentication import (
    ReviewAuthenticationRejected,
    ReviewAuthenticationUnavailable,
)
from document_platform.application.commands import (
    ConflictingReviewResolution,
    InvalidReprocessingDocumentState,
    InvalidReviewResolutionApplication,
    InvalidStagedUpload,
    ReprocessingDocumentNotFound,
    ReprocessingRunNotFound,
    ReprocessingRunNotTerminal,
    ReviewApprovalRequiresCompleteInvoice,
    ReviewCorrectionRequiresApproval,
    ReviewResolutionDocumentNotFound,
    ReviewResolutionRequiresInvoiceExtraction,
    ReviewResolutionRunNotFound,
    UnsupportedDocumentMediaType,
)
from document_platform.application.ports import (
    ActiveProcessingRunAlreadyExists,
    BlobTooLarge,
    EmptyBlob,
    EncryptedPdf,
    InvalidPdf,
    PdfPageLimitExceeded,
    ReprocessingOperationAlreadyExists,
    ReviewResolutionAlreadyExists,
)
from document_platform.application.queries import DocumentNotFound, DocumentSourceUnavailable
from document_platform.application.upload_idempotency import (
    ConflictingIdempotencyKey,
    InvalidIdempotencyKey,
)
from document_platform.domain.documents import InvalidDocument
from document_platform.domain.processing import (
    ConflictingReprocessingIdempotencyKey,
    InvalidReprocessingOperation,
    InvalidReviewResolution,
)


class ProblemDetails(BaseModel):
    type: str
    title: str
    status: int
    detail: str


@dataclass(frozen=True, slots=True)
class ProblemDefinition:
    type: str
    title: str
    status: int
    headers: dict[str, str] | None = None


PROBLEM_DEFINITIONS: tuple[tuple[type[Exception], ProblemDefinition], ...] = (
    (
        DocumentNotFound,
        ProblemDefinition("urn:problem:document-not-found", "Document not found", 404),
    ),
    (
        DocumentSourceUnavailable,
        ProblemDefinition(
            "urn:problem:source-document-unavailable", "Source document unavailable", 503
        ),
    ),
    (
        ReviewAuthenticationRejected,
        ProblemDefinition(
            "urn:problem:operator-authentication-rejected",
            "Operator authentication rejected",
            401,
            headers={"WWW-Authenticate": "Bearer"},
        ),
    ),
    (
        ReviewAuthenticationUnavailable,
        ProblemDefinition(
            "urn:problem:operator-authentication-unavailable",
            "Operator authentication unavailable",
            503,
        ),
    ),
    (
        ReviewResolutionRunNotFound,
        ProblemDefinition("urn:problem:processing-run-not-found", "Processing run not found", 404),
    ),
    (
        ReviewResolutionDocumentNotFound,
        ProblemDefinition("urn:problem:document-not-found", "Document not found", 404),
    ),
    (
        ReprocessingDocumentNotFound,
        ProblemDefinition("urn:problem:document-not-found", "Document not found", 404),
    ),
    (
        ReprocessingRunNotFound,
        ProblemDefinition("urn:problem:reprocessing-unavailable", "Reprocessing unavailable", 409),
    ),
    (
        ReprocessingRunNotTerminal,
        ProblemDefinition("urn:problem:reprocessing-conflict", "Reprocessing unavailable", 409),
    ),
    (
        InvalidReprocessingDocumentState,
        ProblemDefinition("urn:problem:reprocessing-conflict", "Reprocessing unavailable", 409),
    ),
    (
        ActiveProcessingRunAlreadyExists,
        ProblemDefinition("urn:problem:reprocessing-conflict", "Reprocessing unavailable", 409),
    ),
    (
        ReprocessingOperationAlreadyExists,
        ProblemDefinition(
            "urn:problem:reprocessing-idempotency-conflict", "Idempotency conflict", 409
        ),
    ),
    (
        ConflictingReprocessingIdempotencyKey,
        ProblemDefinition(
            "urn:problem:reprocessing-idempotency-conflict", "Idempotency conflict", 409
        ),
    ),
    (
        InvalidReprocessingOperation,
        ProblemDefinition(
            "urn:problem:invalid-reprocessing-request", "Invalid reprocessing request", 422
        ),
    ),
    (
        InvalidReviewResolutionApplication,
        ProblemDefinition(
            "urn:problem:review-resolution-conflict", "Review cannot be resolved", 409
        ),
    ),
    (
        ConflictingReviewResolution,
        ProblemDefinition(
            "urn:problem:review-resolution-conflict", "Review cannot be resolved", 409
        ),
    ),
    (
        ReviewResolutionAlreadyExists,
        ProblemDefinition(
            "urn:problem:review-resolution-conflict", "Review cannot be resolved", 409
        ),
    ),
    (
        ReviewResolutionRequiresInvoiceExtraction,
        ProblemDefinition(
            "urn:problem:review-invoice-incomplete", "Invoice review requires correction", 409
        ),
    ),
    (
        ReviewApprovalRequiresCompleteInvoice,
        ProblemDefinition(
            "urn:problem:review-invoice-incomplete", "Invoice review requires correction", 409
        ),
    ),
    (
        ReviewCorrectionRequiresApproval,
        ProblemDefinition(
            "urn:problem:invalid-review-correction", "Invalid review correction", 422
        ),
    ),
    (
        InvalidIdempotencyKey,
        ProblemDefinition("urn:problem:invalid-idempotency-key", "Invalid idempotency key", 400),
    ),
    (
        ConflictingIdempotencyKey,
        ProblemDefinition("urn:problem:idempotency-conflict", "Idempotency conflict", 409),
    ),
    (
        UnsupportedDocumentMediaType,
        ProblemDefinition("urn:problem:unsupported-media-type", "Unsupported media type", 415),
    ),
    (
        BlobTooLarge,
        ProblemDefinition("urn:problem:document-too-large", "Document too large", 413),
    ),
    (
        EmptyBlob,
        ProblemDefinition("urn:problem:empty-document", "Empty document", 400),
    ),
    (
        EncryptedPdf,
        ProblemDefinition("urn:problem:encrypted-pdf", "Encrypted PDF", 422),
    ),
    (
        PdfPageLimitExceeded,
        ProblemDefinition("urn:problem:pdf-page-limit", "PDF page limit exceeded", 422),
    ),
    (
        InvalidPdf,
        ProblemDefinition("urn:problem:invalid-pdf", "Invalid PDF", 422),
    ),
    (
        InvalidStagedUpload,
        ProblemDefinition("urn:problem:invalid-upload", "Invalid upload", 400),
    ),
    (
        InvalidDocument,
        ProblemDefinition("urn:problem:invalid-document", "Invalid document", 422),
    ),
    (
        InvalidReviewResolution,
        ProblemDefinition(
            "urn:problem:invalid-review-resolution", "Invalid review resolution", 422
        ),
    ),
)


def install_problem_handlers(application: FastAPI) -> None:
    for exception_type, _ in PROBLEM_DEFINITIONS:
        application.add_exception_handler(exception_type, expected_failure_handler)
    application.add_exception_handler(RequestValidationError, request_validation_handler)


async def expected_failure_handler(_request: Request, error: Exception) -> JSONResponse:
    definition = next(
        definition
        for exception_type, definition in PROBLEM_DEFINITIONS
        if isinstance(error, exception_type)
    )
    return _response(definition, detail=str(error))


async def request_validation_handler(
    _request: Request,
    _error: Exception,
) -> JSONResponse:
    return _response(
        ProblemDefinition(
            "urn:problem:request-validation",
            "Request validation failed",
            422,
        ),
        detail="The request does not satisfy the API contract.",
    )


def _response(definition: ProblemDefinition, *, detail: str) -> JSONResponse:
    problem = ProblemDetails(
        type=definition.type,
        title=definition.title,
        status=definition.status,
        detail=detail,
    )
    return JSONResponse(
        status_code=definition.status,
        content=problem.model_dump(),
        media_type="application/problem+json",
        headers=definition.headers,
    )
