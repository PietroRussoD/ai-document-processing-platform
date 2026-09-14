"""SQLAlchemy upload idempotency repository."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from document_platform.adapters.outbound.postgresql.errors import (
    is_unique_violation,
    unique_constraint_name,
)
from document_platform.adapters.outbound.postgresql.models import UploadIdempotencyRecordRow
from document_platform.application.ports import UploadIdempotencyRecordAlreadyExists
from document_platform.application.upload_idempotency import (
    IdempotencyKey,
    UploadIdempotencyRecord,
    UploadRequestFingerprint,
)

IDEMPOTENCY_KEY_CONSTRAINT = "pk_upload_idempotency_records"


class SqlAlchemyUploadIdempotencyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: UploadIdempotencyRecord) -> None:
        self._session.add(_to_row(record))
        try:
            await self._session.flush()
        except IntegrityError as error:
            if (
                is_unique_violation(error)
                and unique_constraint_name(error) == IDEMPOTENCY_KEY_CONSTRAINT
            ):
                raise UploadIdempotencyRecordAlreadyExists(record.key) from error
            raise

    async def get(self, key: IdempotencyKey) -> UploadIdempotencyRecord | None:
        row = await self._session.get(UploadIdempotencyRecordRow, key.value)
        return _to_application(row) if row is not None else None


def _to_row(record: UploadIdempotencyRecord) -> UploadIdempotencyRecordRow:
    return UploadIdempotencyRecordRow(
        idempotency_key=record.key.value,
        request_fingerprint=record.request_fingerprint.value,
        processing_run_id=record.processing_run_id,
        recorded_at=record.recorded_at,
    )


def _to_application(row: UploadIdempotencyRecordRow) -> UploadIdempotencyRecord:
    return UploadIdempotencyRecord(
        key=IdempotencyKey(row.idempotency_key),
        request_fingerprint=UploadRequestFingerprint(row.request_fingerprint),
        processing_run_id=row.processing_run_id,
        recorded_at=row.recorded_at,
    )
