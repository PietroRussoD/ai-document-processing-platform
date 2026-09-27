"""SQLAlchemy repository for immutable AI invoice proposals."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from document_platform.adapters.outbound.postgresql.errors import is_unique_violation
from document_platform.adapters.outbound.postgresql.models import AiInvoiceExtractionProposalRecord
from document_platform.application.ports import InvoiceProposalAlreadyExists
from document_platform.domain.processing import (
    AiInvoiceExtractionProposal,
    InvoiceModelProvider,
    InvoiceProposalField,
    InvoiceProposalIssue,
    InvoiceProposalIssueCode,
    InvoiceProposalStatus,
)


class SqlAlchemyAiInvoiceExtractionProposalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, proposal: AiInvoiceExtractionProposal) -> None:
        self._session.add(_to_record(proposal))
        try:
            await self._session.flush()
        except IntegrityError as error:
            if is_unique_violation(error):
                raise InvoiceProposalAlreadyExists(proposal.processing_run_id) from error
            raise

    async def get(self, processing_run_id: UUID) -> AiInvoiceExtractionProposal | None:
        record = await self._session.get(AiInvoiceExtractionProposalRecord, processing_run_id)
        return _to_domain(record) if record is not None else None


def _to_record(proposal: AiInvoiceExtractionProposal) -> AiInvoiceExtractionProposalRecord:
    return AiInvoiceExtractionProposalRecord(
        processing_run_id=proposal.processing_run_id,
        schema_version=proposal.schema_version,
        provider=proposal.provider.value,
        model_reference=proposal.model_reference,
        model_digest=proposal.model_digest,
        prompt_version=proposal.prompt_version,
        selected_text_sha256=proposal.selected_text_sha256,
        status=proposal.status.value,
        invoice_number=proposal.invoice_number,
        issue_date=proposal.issue_date,
        supplier_name=proposal.supplier_name,
        currency=proposal.currency,
        total_amount=proposal.total_amount,
        issues=[
            {"code": issue.code.value, "field": issue.field.value if issue.field else None}
            for issue in proposal.issues
        ],
        proposed_at=proposal.proposed_at,
    )


def _to_domain(record: AiInvoiceExtractionProposalRecord) -> AiInvoiceExtractionProposal:
    return AiInvoiceExtractionProposal(
        processing_run_id=record.processing_run_id,
        schema_version=record.schema_version,
        provider=InvoiceModelProvider(record.provider),
        model_reference=record.model_reference,
        model_digest=record.model_digest,
        prompt_version=record.prompt_version,
        selected_text_sha256=record.selected_text_sha256,
        status=InvoiceProposalStatus(record.status),
        invoice_number=record.invoice_number,
        issue_date=record.issue_date,
        supplier_name=record.supplier_name,
        currency=record.currency,
        total_amount=record.total_amount,
        issues=tuple(
            InvoiceProposalIssue(
                code=InvoiceProposalIssueCode(issue["code"]),
                field=InvoiceProposalField(issue["field"]) if issue["field"] else None,
            )
            for issue in record.issues
        ),
        proposed_at=record.proposed_at,
    )
