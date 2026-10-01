"""Document-ingestion HTTP endpoints."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, File, Header, Query, Request, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from document_platform.adapters.inbound.http.problems import ProblemDetails
from document_platform.adapters.inbound.http.review_authentication import (
    authenticate_review_operator,
)
from document_platform.adapters.inbound.http.upload_staging import stage_upload
from document_platform.application.commands import (
    AcceptDocumentUpload,
    AcceptDocumentUploadHandler,
    DocumentReprocessingRequested,
    DocumentReviewResolved,
    RequestDocumentReprocessing,
    RequestDocumentReprocessingHandler,
    ResolveDocumentReview,
    ResolveDocumentReviewHandler,
)
from document_platform.application.commands.accept_document_upload import (
    validate_upload_metadata,
)
from document_platform.application.ports import DocumentWorkQueue
from document_platform.application.queries import (
    GetDocumentSourceHandler,
    GetDocumentStatusHandler,
    ListDocumentWorkQueueHandler,
)
from document_platform.domain.documents import DocumentStatus
from document_platform.domain.processing import (
    AiInvoiceProposalExecutionStatus,
    BusinessDocumentType,
    DocumentClassificationReason,
    EmbeddedTextQuality,
    InvoiceExtractionMethod,
    InvoiceModelProvider,
    InvoiceProposalField,
    InvoiceProposalGenerationFailureCode,
    InvoiceProposalIssueCode,
    InvoiceProposalStatus,
    InvoiceReviewCorrectionSource,
    InvoiceReviewField,
    InvoiceReviewFieldCorrection,
    InvoiceValidationDecision,
    InvoiceValidationIssue,
    OcrExtractionMethod,
    ProcessingFailureCode,
    ProcessingRunStatus,
    ProcessingStage,
    ProcessingTextSelectionReason,
    ProcessingTextSource,
    ReviewResolutionDecision,
    TextExtractionMethod,
)
from document_platform.domain.processing.currency_code import is_iso_currency_code
from document_platform.settings import Settings


class AcceptedDocumentResponse(BaseModel):
    document_id: UUID
    processing_run_id: UUID
    accepted_at: datetime
    replayed: bool


class TextExtractionMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    method: TextExtractionMethod
    quality: EmbeddedTextQuality
    page_count: int
    character_count: int
    non_whitespace_character_count: int
    extracted_at: datetime


class OcrExtractionMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    method: OcrExtractionMethod
    page_count: int
    character_count: int
    non_whitespace_character_count: int
    extracted_at: datetime


class TextSelectionMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: ProcessingTextSource
    reason: ProcessingTextSelectionReason
    selected_at: datetime


class ClassificationMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_type: BusinessDocumentType
    reason: DocumentClassificationReason
    classified_at: datetime


class InvoiceExtractionMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    method: InvoiceExtractionMethod
    invoice_number: str | None
    issue_date: date | None
    supplier_name: str | None
    currency: str | None
    total_amount: str | None
    extracted_at: datetime

    @field_validator("total_amount", mode="before")
    @classmethod
    def stringify_total_amount(cls, value: Decimal | str | None) -> str | None:
        return str(value) if value is not None else None


class InvoiceValidationMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision: InvoiceValidationDecision
    issues: tuple[InvoiceValidationIssue, ...]
    validated_at: datetime


class ProcessingOutputResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    embedded_text: TextExtractionMetadataResponse | None
    ocr_text: OcrExtractionMetadataResponse | None
    selected_text: TextSelectionMetadataResponse | None
    classification: ClassificationMetadataResponse | None
    invoice_extraction: InvoiceExtractionMetadataResponse | None
    invoice_validation: InvoiceValidationMetadataResponse | None


class ReviewResolutionMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision: ReviewResolutionDecision
    reviewer_id: str
    review_note: str | None
    resolved_at: datetime
    corrections: tuple["InvoiceReviewCorrectionMetadataResponse", ...]


class InvoiceReviewCorrectionMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    field: InvoiceReviewField
    corrected_value: str
    source: InvoiceReviewCorrectionSource
    corrected_at: datetime

    @field_validator("corrected_value", mode="before")
    @classmethod
    def stringify_corrected_value(cls, value: str | date | Decimal) -> str:
        return str(value)


class ProcessingFailureMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stage: ProcessingStage
    code: ProcessingFailureCode


class AiInvoiceProposalIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: InvoiceProposalIssueCode
    field: InvoiceProposalField | None


class AiInvoiceProposalMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    schema_version: int
    provider: InvoiceModelProvider
    model_reference: str
    model_digest: str | None
    prompt_version: str
    selected_text_sha256: str
    status: InvoiceProposalStatus
    invoice_number: str | None
    issue_date: date | None
    supplier_name: str | None
    currency: str | None
    total_amount: str | None
    issues: tuple[AiInvoiceProposalIssueResponse, ...]
    proposed_at: datetime

    @field_validator("total_amount", mode="before")
    @classmethod
    def stringify_total_amount(cls, value: Decimal | str | None) -> str | None:
        return str(value) if value is not None else None


class AiInvoiceProposalFailureMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: InvoiceModelProvider
    model_reference: str
    code: InvoiceProposalGenerationFailureCode
    failed_at: datetime


class AiInvoiceProposalExecutionMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: AiInvoiceProposalExecutionStatus
    status_changed_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ProcessingRunStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    previous_run_id: UUID | None
    status: ProcessingRunStatus
    queued_at: datetime
    started_at: datetime | None
    status_changed_at: datetime
    finished_at: datetime | None
    attempt_count: int
    failure: ProcessingFailureMetadataResponse | None
    processing_output: ProcessingOutputResponse | None
    review_resolution: ReviewResolutionMetadataResponse | None
    ai_proposal: AiInvoiceProposalMetadataResponse | None
    ai_proposal_failure: AiInvoiceProposalFailureMetadataResponse | None
    ai_execution: AiInvoiceProposalExecutionMetadataResponse | None = Field(
        default=None,
        description=(
            "Persisted advisory AI execution state, independent of document status and proposal "
            "validity. Null means no recorded execution, not disabled: the run may be historical "
            "or may not have entered the AI activity. RUNNING includes slot waits and retries; "
            "it is not a workflow liveness signal."
        ),
    )


class DocumentStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    media_type: str
    size_bytes: int
    page_count: int
    content_sha256: str
    status: DocumentStatus
    accepted_at: datetime
    status_changed_at: datetime
    current_run: ProcessingRunStatusResponse


class DocumentWorkQueueItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: UUID
    original_filename: str
    status: DocumentStatus
    accepted_at: datetime
    status_changed_at: datetime
    processing_run_id: UUID
    processing_run_status: ProcessingRunStatus
    queued_at: datetime
    started_at: datetime | None
    attempt_count: int
    failure: ProcessingFailureMetadataResponse | None


class DocumentWorkQueuePageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: tuple[DocumentWorkQueueItemResponse, ...]
    total: int
    limit: int
    offset: int


class InvoiceNumberReviewCorrectionRequest(BaseModel):
    field: Literal[InvoiceReviewField.INVOICE_NUMBER]
    corrected_value: str = Field(min_length=1, max_length=128)
    source: InvoiceReviewCorrectionSource = InvoiceReviewCorrectionSource.MANUAL

    @field_validator("corrected_value")
    @classmethod
    def reject_blank_value(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("corrected_value must not be blank")
        return value


class IssueDateReviewCorrectionRequest(BaseModel):
    field: Literal[InvoiceReviewField.ISSUE_DATE]
    corrected_value: date
    source: InvoiceReviewCorrectionSource = InvoiceReviewCorrectionSource.MANUAL


class SupplierNameReviewCorrectionRequest(BaseModel):
    field: Literal[InvoiceReviewField.SUPPLIER_NAME]
    corrected_value: str = Field(min_length=1, max_length=512)
    source: InvoiceReviewCorrectionSource = InvoiceReviewCorrectionSource.MANUAL

    @field_validator("corrected_value")
    @classmethod
    def reject_blank_value(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("corrected_value must not be blank")
        return value


class CurrencyReviewCorrectionRequest(BaseModel):
    field: Literal[InvoiceReviewField.CURRENCY]
    corrected_value: str = Field(
        pattern=r"^[A-Z]{3}$",
        description="ISO 4217 alpha currency code.",
    )
    source: InvoiceReviewCorrectionSource = InvoiceReviewCorrectionSource.MANUAL

    @field_validator("corrected_value")
    @classmethod
    def validate_iso_currency_code(cls, value: str) -> str:
        if not is_iso_currency_code(value):
            raise ValueError("corrected_value must be an ISO 4217 alpha code")
        return value


class TotalAmountReviewCorrectionRequest(BaseModel):
    field: Literal[InvoiceReviewField.TOTAL_AMOUNT]
    corrected_value: Decimal = Field(gt=Decimal("0"), max_digits=20, decimal_places=4)
    source: InvoiceReviewCorrectionSource = InvoiceReviewCorrectionSource.MANUAL


type InvoiceReviewCorrectionRequest = Annotated[
    InvoiceNumberReviewCorrectionRequest
    | IssueDateReviewCorrectionRequest
    | SupplierNameReviewCorrectionRequest
    | CurrencyReviewCorrectionRequest
    | TotalAmountReviewCorrectionRequest,
    Field(discriminator="field"),
]


class ResolveDocumentReviewRequest(BaseModel):
    decision: ReviewResolutionDecision
    review_note: str | None = Field(default=None, max_length=2_000)
    corrections: tuple[InvoiceReviewCorrectionRequest, ...] = ()


class ReviewResolutionResponse(BaseModel):
    processing_run_id: UUID
    decision: ReviewResolutionDecision
    reviewer_id: str
    resolved_at: datetime
    replayed: bool


class RequestDocumentReprocessingRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class DocumentReprocessingResponse(BaseModel):
    operation_id: UUID
    document_id: UUID
    source_run_id: UUID
    replacement_run_id: UUID
    requested_at: datetime
    replayed: bool


router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])


def _problem_response(description: str) -> dict[str, Any]:
    return {
        "description": description,
        "content": {
            "application/problem+json": {
                "schema": ProblemDetails.model_json_schema(),
            }
        },
    }


@router.get(
    "",
    operation_id="listDocumentWorkQueue",
    summary="List a page from an operator document work queue",
)
async def list_document_work_queue(
    request: Request,
    queue: Annotated[DocumentWorkQueue, Query()],
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> DocumentWorkQueuePageResponse:
    handler = cast(ListDocumentWorkQueueHandler, request.app.state.list_document_work_queue)
    page = await handler(queue, limit=limit, offset=offset)
    return DocumentWorkQueuePageResponse.model_validate(page)


@router.get(
    "/{document_id}",
    operation_id="getDocumentStatus",
    summary="Get the current document and processing status",
    responses={404: _problem_response("Not Found")},
)
async def get_document_status(
    document_id: UUID,
    request: Request,
) -> DocumentStatusResponse:
    handler = cast(GetDocumentStatusHandler, request.app.state.get_document_status)
    document = await handler(document_id)
    return DocumentStatusResponse.model_validate(document)


@router.get(
    "/{document_id}/source",
    operation_id="getDocumentSource",
    summary="Retrieve a source PDF for local operator review",
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}},
        401: _problem_response("Unauthorized"),
        404: _problem_response("Not Found"),
        503: _problem_response("Service Unavailable"),
    },
)
async def get_document_source(
    document_id: UUID,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    settings = cast(Settings, request.app.state.settings)
    authenticate_review_operator(authorization=authorization, settings=settings)
    handler = cast(GetDocumentSourceHandler, request.app.state.get_document_source)
    content = await handler(document_id)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'inline; filename="document.pdf"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/{document_id}/review-resolution",
    operation_id="resolveDocumentReview",
    summary="Approve or reject a document requiring review",
    responses={
        401: _problem_response("Unauthorized"),
        404: _problem_response("Not Found"),
        409: _problem_response("Conflict"),
        422: _problem_response("Unprocessable Content"),
        503: _problem_response("Service Unavailable"),
    },
)
async def resolve_document_review(
    document_id: UUID,
    resolution: ResolveDocumentReviewRequest,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> ReviewResolutionResponse:
    settings = cast(Settings, request.app.state.settings)
    operator = authenticate_review_operator(authorization=authorization, settings=settings)
    get_status = cast(GetDocumentStatusHandler, request.app.state.get_document_status)
    document = await get_status(document_id)
    handler = cast(ResolveDocumentReviewHandler, request.app.state.resolve_document_review)
    resolved = await handler(
        ResolveDocumentReview(
            processing_run_id=document.current_run.id,
            decision=resolution.decision,
            reviewer_id=operator.reviewer_id,
            review_note=resolution.review_note,
            corrections=tuple(
                InvoiceReviewFieldCorrection(
                    field=correction.field,
                    corrected_value=correction.corrected_value,
                    source=correction.source,
                )
                for correction in resolution.corrections
            ),
        )
    )
    return _review_resolution_response(resolved)


@router.post(
    "/{document_id}/reprocessing-requests",
    operation_id="requestDocumentReprocessing",
    summary="Request controlled reprocessing for a completed document",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        401: _problem_response("Unauthorized"),
        404: _problem_response("Not Found"),
        409: _problem_response("Conflict"),
        422: _problem_response("Unprocessable Content"),
        503: _problem_response("Service Unavailable"),
    },
)
async def request_document_reprocessing(
    document_id: UUID,
    reprocessing_request: RequestDocumentReprocessingRequest,
    request: Request,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    authorization: Annotated[str | None, Header()] = None,
) -> DocumentReprocessingResponse:
    settings = cast(Settings, request.app.state.settings)
    operator = authenticate_review_operator(authorization=authorization, settings=settings)
    handler = cast(
        RequestDocumentReprocessingHandler,
        request.app.state.request_document_reprocessing,
    )
    reprocessing = await handler(
        RequestDocumentReprocessing(
            document_id=document_id,
            requested_by=operator.reviewer_id,
            reason=reprocessing_request.reason,
            idempotency_key=idempotency_key,
        )
    )
    return _document_reprocessing_response(reprocessing)


@router.post(
    "",
    operation_id="acceptDocumentUpload",
    summary="Accept a PDF for asynchronous processing",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: _problem_response("Bad Request"),
        409: _problem_response("Conflict"),
        413: _problem_response("Content Too Large"),
        415: _problem_response("Unsupported Media Type"),
        422: _problem_response("Unprocessable Content"),
    },
)
async def accept_document_upload(
    request: Request,
    document: Annotated[UploadFile, File(description="PDF document")],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> AcceptedDocumentResponse:
    settings = cast(Settings, request.app.state.settings)
    handler = cast(AcceptDocumentUploadHandler, request.app.state.accept_document_upload)
    original_filename = document.filename or ""
    declared_media_type = document.content_type or ""
    validate_upload_metadata(
        idempotency_key=idempotency_key,
        original_filename=original_filename,
        declared_media_type=declared_media_type,
    )

    async with stage_upload(
        document,
        storage_root=settings.storage_root,
        max_bytes=settings.max_document_bytes,
    ) as staged_path:
        accepted = await handler(
            AcceptDocumentUpload(
                idempotency_key=idempotency_key,
                original_filename=original_filename,
                declared_media_type=declared_media_type,
                staged_path=staged_path,
            )
        )

    return AcceptedDocumentResponse(
        document_id=accepted.document_id,
        processing_run_id=accepted.processing_run_id,
        accepted_at=accepted.accepted_at,
        replayed=accepted.replayed,
    )


def _review_resolution_response(resolved: DocumentReviewResolved) -> ReviewResolutionResponse:
    return ReviewResolutionResponse(
        processing_run_id=resolved.processing_run_id,
        decision=resolved.decision,
        reviewer_id=resolved.reviewer_id,
        resolved_at=resolved.resolved_at,
        replayed=resolved.replayed,
    )


def _document_reprocessing_response(
    requested: DocumentReprocessingRequested,
) -> DocumentReprocessingResponse:
    return DocumentReprocessingResponse(
        operation_id=requested.operation_id,
        document_id=requested.document_id,
        source_run_id=requested.source_run_id,
        replacement_run_id=requested.replacement_run_id,
        requested_at=requested.requested_at,
        replayed=requested.replayed,
    )
