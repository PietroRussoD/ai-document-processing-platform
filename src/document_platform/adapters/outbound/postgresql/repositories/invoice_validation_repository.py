"""SQLAlchemy repository for immutable invoice validations."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from document_platform.adapters.outbound.postgresql.errors import is_unique_violation
from document_platform.adapters.outbound.postgresql.models import InvoiceValidationRecord
from document_platform.application.ports import InvoiceValidationAlreadyExists
from document_platform.domain.processing import (
    InvoiceValidation,
    InvoiceValidationDecision,
    InvoiceValidationIssue,
)


class SqlAlchemyInvoiceValidationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, validation: InvoiceValidation) -> None:
        self._session.add(_to_record(validation))
        try:
            await self._session.flush()
        except IntegrityError as error:
            if is_unique_violation(error):
                raise InvoiceValidationAlreadyExists(validation.processing_run_id) from error
            raise

    async def get(self, processing_run_id: UUID) -> InvoiceValidation | None:
        record = await self._session.get(InvoiceValidationRecord, processing_run_id)
        return _to_domain(record) if record is not None else None


def _to_record(validation: InvoiceValidation) -> InvoiceValidationRecord:
    return InvoiceValidationRecord(
        processing_run_id=validation.processing_run_id,
        decision=validation.decision.value,
        issues=[issue.value for issue in validation.issues],
        validated_at=validation.validated_at,
    )


def _to_domain(record: InvoiceValidationRecord) -> InvoiceValidation:
    return InvoiceValidation(
        processing_run_id=record.processing_run_id,
        decision=InvoiceValidationDecision(record.decision),
        issues=tuple(InvoiceValidationIssue(issue) for issue in record.issues),
        validated_at=record.validated_at,
    )
