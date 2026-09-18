"""SQLAlchemy repository for immutable operator invoice corrections."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from document_platform.adapters.outbound.postgresql.errors import is_unique_violation
from document_platform.adapters.outbound.postgresql.models import InvoiceReviewCorrectionRecord
from document_platform.application.ports import InvoiceReviewCorrectionAlreadyExists
from document_platform.domain.processing import (
    InvoiceReviewCorrection,
    InvoiceReviewField,
    InvoiceReviewFieldCorrection,
)


class SqlAlchemyInvoiceReviewCorrectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, correction: InvoiceReviewCorrection) -> None:
        self._session.add_all(_to_records(correction))
        try:
            await self._session.flush()
        except IntegrityError as error:
            if is_unique_violation(error):
                raise InvoiceReviewCorrectionAlreadyExists(correction.processing_run_id) from error
            raise

    async def get(self, processing_run_id: UUID) -> InvoiceReviewCorrection | None:
        records = (
            await self._session.scalars(
                select(InvoiceReviewCorrectionRecord)
                .where(InvoiceReviewCorrectionRecord.processing_run_id == processing_run_id)
                .order_by(InvoiceReviewCorrectionRecord.field)
            )
        ).all()
        if not records:
            return None
        return InvoiceReviewCorrection(
            processing_run_id=processing_run_id,
            corrections=tuple(_to_domain_correction(record) for record in records),
            corrected_at=records[0].corrected_at,
        )


def _to_records(correction: InvoiceReviewCorrection) -> list[InvoiceReviewCorrectionRecord]:
    return [
        _to_record(correction=correction, field_correction=field_correction)
        for field_correction in correction.corrections
    ]


def _to_record(
    *,
    correction: InvoiceReviewCorrection,
    field_correction: InvoiceReviewFieldCorrection,
) -> InvoiceReviewCorrectionRecord:
    value = field_correction.corrected_value
    return InvoiceReviewCorrectionRecord(
        processing_run_id=correction.processing_run_id,
        field=field_correction.field.value,
        corrected_text=value if isinstance(value, str) else None,
        corrected_date=(value if field_correction.field is InvoiceReviewField.ISSUE_DATE else None),
        corrected_amount=(
            value if field_correction.field is InvoiceReviewField.TOTAL_AMOUNT else None
        ),
        corrected_at=correction.corrected_at,
    )


def _to_domain_correction(
    record: InvoiceReviewCorrectionRecord,
) -> InvoiceReviewFieldCorrection:
    field = InvoiceReviewField(record.field)
    if field is InvoiceReviewField.ISSUE_DATE:
        if record.corrected_date is None:
            raise RuntimeError("persisted ISSUE_DATE correction is missing corrected_date")
        value = record.corrected_date
    elif field is InvoiceReviewField.TOTAL_AMOUNT:
        if record.corrected_amount is None:
            raise RuntimeError("persisted TOTAL_AMOUNT correction is missing corrected_amount")
        value = record.corrected_amount
    else:
        if record.corrected_text is None:
            raise RuntimeError("persisted text correction is missing corrected_text")
        value = record.corrected_text
    return InvoiceReviewFieldCorrection(field=field, corrected_value=value)
