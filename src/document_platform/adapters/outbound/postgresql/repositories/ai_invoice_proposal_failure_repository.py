"""SQLAlchemy repository for terminal AI proposal provider failures."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from document_platform.adapters.outbound.postgresql.errors import is_unique_violation
from document_platform.adapters.outbound.postgresql.models import (
    AiInvoiceExtractionProposalRecord,
    AiInvoiceProposalFailureRecord,
    ProcessingRunRecord,
)
from document_platform.application.ports import (
    InvoiceProposalFailureAlreadyExists,
    InvoiceProposalOutcomeConflict,
)
from document_platform.domain.processing import (
    AiInvoiceProposalFailure,
    InvoiceModelProvider,
    InvoiceProposalGenerationFailureCode,
)


class SqlAlchemyAiInvoiceProposalFailureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, failure: AiInvoiceProposalFailure) -> None:
        await self._session.scalar(
            select(ProcessingRunRecord.id)
            .where(ProcessingRunRecord.id == failure.processing_run_id)
            .with_for_update()
        )
        if await self._session.get(AiInvoiceExtractionProposalRecord, failure.processing_run_id):
            raise InvoiceProposalOutcomeConflict(failure.processing_run_id)
        self._session.add(
            AiInvoiceProposalFailureRecord(
                processing_run_id=failure.processing_run_id,
                provider=failure.provider.value,
                model_reference=failure.model_reference,
                code=failure.code.value,
                failed_at=failure.failed_at,
            )
        )
        try:
            await self._session.flush()
        except IntegrityError as error:
            if is_unique_violation(error):
                raise InvoiceProposalFailureAlreadyExists(failure.processing_run_id) from error
            raise

    async def get(self, processing_run_id: UUID) -> AiInvoiceProposalFailure | None:
        record = await self._session.get(AiInvoiceProposalFailureRecord, processing_run_id)
        if record is None:
            return None
        return AiInvoiceProposalFailure(
            processing_run_id=record.processing_run_id,
            provider=InvoiceModelProvider(record.provider),
            model_reference=record.model_reference,
            code=InvoiceProposalGenerationFailureCode(record.code),
            failed_at=record.failed_at,
        )
