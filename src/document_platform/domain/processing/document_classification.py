"""Deterministic business-document classification rules."""

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class BusinessDocumentType(StrEnum):
    INVOICE = "INVOICE"
    PURCHASE_ORDER = "PURCHASE_ORDER"
    CREDIT_NOTE = "CREDIT_NOTE"
    UNKNOWN = "UNKNOWN"


class DocumentClassificationReason(StrEnum):
    KEYWORD_MATCHED = "KEYWORD_MATCHED"
    NO_MATCH = "NO_MATCH"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"


class InvalidDocumentClassification(ValueError):
    """Raised when a classification record violates a domain invariant."""


@dataclass(frozen=True, slots=True)
class DocumentClassification:
    processing_run_id: UUID
    document_type: BusinessDocumentType
    reason: DocumentClassificationReason
    classified_at: datetime

    def __post_init__(self) -> None:
        if self.processing_run_id.int == 0:
            raise InvalidDocumentClassification("processing_run_id must not be the nil UUID")
        if self.classified_at.tzinfo is None or self.classified_at.utcoffset() is None:
            raise InvalidDocumentClassification("classified_at must be timezone-aware")
        if (self.document_type is BusinessDocumentType.UNKNOWN) != (
            self.reason is not DocumentClassificationReason.KEYWORD_MATCHED
        ):
            raise InvalidDocumentClassification(
                "unknown type is required exactly for non-keyword classification reasons"
            )


class DocumentClassificationPolicy:
    _TERMS: dict[BusinessDocumentType, tuple[str, ...]] = {
        BusinessDocumentType.INVOICE: ("invoice", "fattura"),
        BusinessDocumentType.PURCHASE_ORDER: ("purchase order", "ordine di acquisto"),
        BusinessDocumentType.CREDIT_NOTE: ("credit note", "nota di credito"),
    }

    def classify(
        self,
        *,
        processing_run_id: UUID,
        text: str,
        classified_at: datetime,
    ) -> DocumentClassification:
        normalized = text.casefold()
        matches = tuple(
            document_type
            for document_type, terms in self._TERMS.items()
            if any(re.search(rf"\b{re.escape(term)}\b", normalized) for term in terms)
        )
        if len(matches) == 1:
            return DocumentClassification(
                processing_run_id=processing_run_id,
                document_type=matches[0],
                reason=DocumentClassificationReason.KEYWORD_MATCHED,
                classified_at=classified_at,
            )
        return DocumentClassification(
            processing_run_id=processing_run_id,
            document_type=BusinessDocumentType.UNKNOWN,
            reason=(
                DocumentClassificationReason.NO_MATCH
                if not matches
                else DocumentClassificationReason.AMBIGUOUS_MATCH
            ),
            classified_at=classified_at,
        )
