"""Document-status read model contract."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from document_platform.domain.documents import DocumentStatus
from document_platform.domain.processing import (
    BusinessDocumentType,
    DocumentClassificationReason,
    EmbeddedTextQuality,
    InvoiceExtractionMethod,
    InvoiceReviewField,
    InvoiceValidationDecision,
    InvoiceValidationIssue,
    OcrExtractionMethod,
    ProcessingRunStatus,
    ProcessingTextSelectionReason,
    ProcessingTextSource,
    ReviewResolutionDecision,
    TextExtractionMethod,
)


@dataclass(frozen=True, slots=True)
class TextExtractionMetadataView:
    method: TextExtractionMethod
    quality: EmbeddedTextQuality
    page_count: int
    character_count: int
    non_whitespace_character_count: int
    extracted_at: datetime


@dataclass(frozen=True, slots=True)
class OcrExtractionMetadataView:
    method: OcrExtractionMethod
    page_count: int
    character_count: int
    non_whitespace_character_count: int
    extracted_at: datetime


@dataclass(frozen=True, slots=True)
class TextSelectionMetadataView:
    source: ProcessingTextSource
    reason: ProcessingTextSelectionReason
    selected_at: datetime


@dataclass(frozen=True, slots=True)
class ClassificationMetadataView:
    document_type: BusinessDocumentType
    reason: DocumentClassificationReason
    classified_at: datetime


@dataclass(frozen=True, slots=True)
class InvoiceExtractionMetadataView:
    method: InvoiceExtractionMethod
    invoice_number: str | None
    issue_date: date | None
    supplier_name: str | None
    currency: str | None
    total_amount: Decimal | None
    extracted_at: datetime


@dataclass(frozen=True, slots=True)
class InvoiceValidationMetadataView:
    decision: InvoiceValidationDecision
    issues: tuple[InvoiceValidationIssue, ...]
    validated_at: datetime


@dataclass(frozen=True, slots=True)
class ProcessingOutputView:
    embedded_text: TextExtractionMetadataView | None
    ocr_text: OcrExtractionMetadataView | None
    selected_text: TextSelectionMetadataView | None
    classification: ClassificationMetadataView | None
    invoice_extraction: InvoiceExtractionMetadataView | None
    invoice_validation: InvoiceValidationMetadataView | None


@dataclass(frozen=True, slots=True)
class InvoiceReviewCorrectionMetadataView:
    field: InvoiceReviewField
    corrected_value: str | date | Decimal
    corrected_at: datetime


@dataclass(frozen=True, slots=True)
class ReviewResolutionMetadataView:
    decision: ReviewResolutionDecision
    reviewer_id: str
    review_note: str | None
    resolved_at: datetime
    corrections: tuple[InvoiceReviewCorrectionMetadataView, ...]


@dataclass(frozen=True, slots=True)
class ProcessingRunStatusView:
    id: UUID
    status: ProcessingRunStatus
    queued_at: datetime
    started_at: datetime | None
    status_changed_at: datetime
    finished_at: datetime | None
    attempt_count: int
    processing_output: ProcessingOutputView | None
    review_resolution: ReviewResolutionMetadataView | None


@dataclass(frozen=True, slots=True)
class DocumentStatusView:
    id: UUID
    original_filename: str
    media_type: str
    size_bytes: int
    page_count: int
    content_sha256: str
    status: DocumentStatus
    accepted_at: datetime
    status_changed_at: datetime
    current_run: ProcessingRunStatusView


class DocumentStatusReader(Protocol):
    async def get(self, document_id: UUID) -> DocumentStatusView | None: ...
