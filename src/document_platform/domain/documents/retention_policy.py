"""Status eligibility rules for document retention."""

from document_platform.domain.documents.document import DocumentStatus

RETENTION_ELIGIBLE_STATUSES = frozenset(
    {
        DocumentStatus.APPROVED,
        DocumentStatus.REJECTED,
        DocumentStatus.FAILED,
        DocumentStatus.UNSUPPORTED,
    }
)
