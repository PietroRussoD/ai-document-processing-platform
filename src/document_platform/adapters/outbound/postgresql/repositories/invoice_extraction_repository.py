"""SQLAlchemy repository for immutable structured invoice extractions."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from document_platform.adapters.outbound.postgresql.errors import is_unique_violation
from document_platform.adapters.outbound.postgresql.models import InvoiceExtractionRecord
from document_platform.application.ports import InvoiceExtractionAlreadyExists
from document_platform.domain.processing import InvoiceExtraction, InvoiceExtractionMethod


class SqlAlchemyInvoiceExtractionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, extraction: InvoiceExtraction) -> None:
        self._session.add(_to_record(extraction))
        try:
            await self._session.flush()
        except IntegrityError as error:
            if is_unique_violation(error):
                raise InvoiceExtractionAlreadyExists(extraction.processing_run_id) from error
            raise

    async def get(self, processing_run_id: UUID) -> InvoiceExtraction | None:
        record = await self._session.get(InvoiceExtractionRecord, processing_run_id)
        return _to_domain(record) if record is not None else None


def _to_record(extraction: InvoiceExtraction) -> InvoiceExtractionRecord:
    return InvoiceExtractionRecord(
        processing_run_id=extraction.processing_run_id,
        method=extraction.method.value,
        invoice_number=extraction.invoice_number,
        issue_date=extraction.issue_date,
        supplier_name=extraction.supplier_name,
        currency=extraction.currency,
        total_amount=extraction.total_amount,
        extracted_at=extraction.extracted_at,
    )


def _to_domain(record: InvoiceExtractionRecord) -> InvoiceExtraction:
    return InvoiceExtraction(
        processing_run_id=record.processing_run_id,
        method=InvoiceExtractionMethod(record.method),
        invoice_number=record.invoice_number,
        issue_date=record.issue_date,
        supplier_name=record.supplier_name,
        currency=record.currency,
        total_amount=record.total_amount,
        extracted_at=record.extracted_at,
    )
