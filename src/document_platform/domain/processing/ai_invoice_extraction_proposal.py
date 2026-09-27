"""Immutable, provenance-aware invoice fields proposed by a local model."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class InvoiceProposalStatus(StrEnum):
    VALID = "VALID"
    PARTIAL = "PARTIAL"
    INVALID = "INVALID"


class InvoiceProposalField(StrEnum):
    INVOICE_NUMBER = "INVOICE_NUMBER"
    ISSUE_DATE = "ISSUE_DATE"
    SUPPLIER_NAME = "SUPPLIER_NAME"
    CURRENCY = "CURRENCY"
    TOTAL_AMOUNT = "TOTAL_AMOUNT"


class InvoiceProposalIssueCode(StrEnum):
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
    MISSING_FIELD = "MISSING_FIELD"
    INVALID_FIELD_VALUE = "INVALID_FIELD_VALUE"


class InvoiceModelProvider(StrEnum):
    OLLAMA = "OLLAMA"


class InvalidInvoiceExtractionProposal(ValueError):
    """Raised when a model proposal violates its versioned domain contract."""


@dataclass(frozen=True, slots=True)
class InvoiceProposalIssue:
    code: InvoiceProposalIssueCode
    field: InvoiceProposalField | None

    def __post_init__(self) -> None:
        if self.code is InvoiceProposalIssueCode.MALFORMED_RESPONSE and self.field is not None:
            raise InvalidInvoiceExtractionProposal(
                "MALFORMED_RESPONSE must not identify an invoice field"
            )
        if self.code is not InvoiceProposalIssueCode.MALFORMED_RESPONSE and self.field is None:
            raise InvalidInvoiceExtractionProposal(f"{self.code} must identify an invoice field")


@dataclass(frozen=True, slots=True)
class AiInvoiceExtractionProposal:
    processing_run_id: UUID
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
    total_amount: Decimal | None
    issues: tuple[InvoiceProposalIssue, ...]
    proposed_at: datetime

    def __post_init__(self) -> None:
        if self.processing_run_id.int == 0:
            raise InvalidInvoiceExtractionProposal("processing_run_id must not be the nil UUID")
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise InvalidInvoiceExtractionProposal("schema_version must be 1")
        if not self.model_reference.strip() or len(self.model_reference) > 200:
            raise InvalidInvoiceExtractionProposal(
                "model_reference must contain 1 to 200 characters"
            )
        if self.model_digest is not None and not re.fullmatch(
            r"(?:sha256:)?[0-9a-fA-F]{64}", self.model_digest
        ):
            raise InvalidInvoiceExtractionProposal("model_digest must be a SHA-256 digest")
        if not self.prompt_version.strip() or len(self.prompt_version) > 100:
            raise InvalidInvoiceExtractionProposal(
                "prompt_version must contain 1 to 100 characters"
            )
        if not re.fullmatch(r"[0-9a-f]{64}", self.selected_text_sha256):
            raise InvalidInvoiceExtractionProposal(
                "selected_text_sha256 must be a lowercase SHA-256"
            )
        if self.invoice_number is not None:
            if not self.invoice_number.strip():
                raise InvalidInvoiceExtractionProposal("invoice_number must be non-blank text")
            if len(self.invoice_number) > 200:
                raise InvalidInvoiceExtractionProposal(
                    "invoice_number must not exceed 200 characters"
                )
        if self.supplier_name is not None:
            if not self.supplier_name.strip():
                raise InvalidInvoiceExtractionProposal("supplier_name must be non-blank text")
            if len(self.supplier_name) > 250:
                raise InvalidInvoiceExtractionProposal(
                    "supplier_name must not exceed 250 characters"
                )
        if self.issue_date is not None and (isinstance(self.issue_date, datetime)):
            raise InvalidInvoiceExtractionProposal("issue_date must be a date")
        if self.currency is not None and not _is_iso_currency_code(self.currency):
            raise InvalidInvoiceExtractionProposal(
                "currency must be an uppercase ISO 4217 alpha code"
            )
        if self.total_amount is not None:
            _validate_total_amount(self.total_amount)
        if not _is_timezone_aware(self.proposed_at):
            raise InvalidInvoiceExtractionProposal("proposed_at must be timezone-aware")
        if type(self.issues) is not tuple:
            raise InvalidInvoiceExtractionProposal("issues must be a tuple")
        if len(set(self.issues)) != len(self.issues):
            raise InvalidInvoiceExtractionProposal("issues must not contain duplicates")
        _validate_proposal_state(self)


def _validate_proposal_state(proposal: AiInvoiceExtractionProposal) -> None:
    values = (
        proposal.invoice_number,
        proposal.issue_date,
        proposal.supplier_name,
        proposal.currency,
        proposal.total_amount,
    )
    proposed_count = sum(value is not None for value in values)

    if proposal.status is InvoiceProposalStatus.VALID:
        if proposed_count != len(values) or proposal.issues:
            raise InvalidInvoiceExtractionProposal(
                "VALID proposals require every field and must not contain issues"
            )
    elif proposal.status is InvoiceProposalStatus.PARTIAL:
        if proposed_count == 0 or not proposal.issues:
            raise InvalidInvoiceExtractionProposal(
                "PARTIAL proposals require at least one field and one issue"
            )
    elif proposal.status is InvoiceProposalStatus.INVALID and (
        proposed_count != 0 or not proposal.issues
    ):
        raise InvalidInvoiceExtractionProposal(
            "INVALID proposals require no fields and at least one issue"
        )


def _validate_total_amount(value: Decimal) -> None:
    if not value.is_finite() or value < Decimal("0"):
        raise InvalidInvoiceExtractionProposal("total_amount must be finite and non-negative")
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int) or -exponent > 4:
        raise InvalidInvoiceExtractionProposal("total_amount must have at most four decimal places")


def _is_iso_currency_code(value: str) -> bool:
    return len(value) == 3 and value.isascii() and value.isalpha() and value.isupper()


def _is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None
