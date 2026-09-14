"""Document-ingestion HTTP endpoints."""

from datetime import datetime
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, File, Header, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict

from document_platform.adapters.inbound.http.problems import ProblemDetails
from document_platform.adapters.inbound.http.upload_staging import stage_upload
from document_platform.application.commands import (
    AcceptDocumentUpload,
    AcceptDocumentUploadHandler,
)
from document_platform.application.commands.accept_document_upload import (
    validate_upload_metadata,
)
from document_platform.application.queries import GetDocumentStatusHandler
from document_platform.domain.documents import DocumentStatus
from document_platform.domain.processing import ProcessingRunStatus
from document_platform.settings import Settings


class AcceptedDocumentResponse(BaseModel):
    document_id: UUID
    processing_run_id: UUID
    accepted_at: datetime
    replayed: bool


class ProcessingRunStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: ProcessingRunStatus
    queued_at: datetime
    started_at: datetime | None
    status_changed_at: datetime
    finished_at: datetime | None
    attempt_count: int


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
