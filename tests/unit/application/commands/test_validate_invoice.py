"""Invoice-validation application tests."""

from datetime import UTC, date, datetime
from decimal import Decimal
from types import TracebackType
from typing import Self, cast
from uuid import UUID

import pytest

from document_platform.application.commands.validate_invoice import (
    InvoiceValidated,
    InvoiceValidationRequiresExtraction,
    ValidateInvoice,
    ValidateInvoiceHandler,
)
from document_platform.application.ports import InvoiceValidationAlreadyExists, UnitOfWork
from document_platform.domain.processing import (
    InvoiceExtraction,
    InvoiceExtractionMethod,
    InvoiceValidation,
    InvoiceValidationDecision,
    InvoiceValidationIssue,
    InvoiceValidationPolicy,
)

AT = datetime(2026, 9, 17, 10, 0, tzinfo=UTC)
RUN_ID = UUID("d8d8d8d8-d8d8-48d8-88d8-d8d8d8d8d8d8")


class ValueRepository:
    def __init__(self, value: object | None = None) -> None:
        self.value = value
        self.added: list[object] = []

    async def add(self, value: object) -> None:
        self.value = value
        self.added.append(value)

    async def get(self, processing_run_id: UUID) -> object | None:
        return self.value


class DuplicateInvoiceValidationRepository(ValueRepository):
    async def add(self, value: object) -> None:
        raise InvoiceValidationAlreadyExists(RUN_ID)


class RecordingUnitOfWork:
    def __init__(self) -> None:
        self.invoice_extractions = ValueRepository(valid_invoice_extraction())
        self.invoice_validations = ValueRepository()
        self.commit_count = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def commit(self) -> None:
        self.commit_count += 1


def valid_invoice_extraction() -> InvoiceExtraction:
    return InvoiceExtraction(
        processing_run_id=RUN_ID,
        method=InvoiceExtractionMethod.DETERMINISTIC_RULES,
        invoice_number="INV-42",
        issue_date=date(2026, 9, 17),
        supplier_name="Acme Ltd",
        currency="EUR",
        total_amount=Decimal("12.50"),
        extracted_at=AT,
    )


def handler(unit_of_work: RecordingUnitOfWork) -> ValidateInvoiceHandler:
    return ValidateInvoiceHandler(
        unit_of_work_factory=lambda: cast(UnitOfWork, unit_of_work),
        validation_policy=InvoiceValidationPolicy(),
        clock=lambda: AT,
    )


@pytest.mark.anyio
async def test_validates_and_persists_a_complete_invoice() -> None:
    unit_of_work = RecordingUnitOfWork()

    result = await handler(unit_of_work)(ValidateInvoice(RUN_ID))

    assert result == InvoiceValidated(
        RUN_ID,
        InvoiceValidationDecision.AUTO_APPROVE,
        replayed=False,
    )
    validation = cast(InvoiceValidation, unit_of_work.invoice_validations.added[0])
    assert validation.issues == ()
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_marks_an_incomplete_invoice_for_review() -> None:
    unit_of_work = RecordingUnitOfWork()
    unit_of_work.invoice_extractions.value = InvoiceExtraction(
        processing_run_id=RUN_ID,
        method=InvoiceExtractionMethod.DETERMINISTIC_RULES,
        invoice_number="INV-42",
        issue_date=None,
        supplier_name="Acme Ltd",
        currency=None,
        total_amount=None,
        extracted_at=AT,
    )

    result = await handler(unit_of_work)(ValidateInvoice(RUN_ID))

    assert result == InvoiceValidated(
        RUN_ID,
        InvoiceValidationDecision.REVIEW_REQUIRED,
        replayed=False,
    )
    validation = cast(InvoiceValidation, unit_of_work.invoice_validations.added[0])
    assert validation.issues == (
        InvoiceValidationIssue.MISSING_ISSUE_DATE,
        InvoiceValidationIssue.MISSING_CURRENCY,
        InvoiceValidationIssue.MISSING_TOTAL_AMOUNT,
    )


@pytest.mark.anyio
async def test_replay_reuses_the_persisted_validation() -> None:
    unit_of_work = RecordingUnitOfWork()
    command = ValidateInvoice(RUN_ID)

    await handler(unit_of_work)(command)
    replay = await handler(unit_of_work)(command)

    assert replay == InvoiceValidated(RUN_ID, InvoiceValidationDecision.AUTO_APPROVE, replayed=True)
    assert unit_of_work.commit_count == 1


@pytest.mark.anyio
async def test_concurrent_persist_returns_the_existing_validation() -> None:
    unit_of_work = RecordingUnitOfWork()
    persisted = InvoiceValidation(
        processing_run_id=RUN_ID,
        decision=InvoiceValidationDecision.AUTO_APPROVE,
        issues=(),
        validated_at=AT,
    )
    unit_of_work.invoice_validations = DuplicateInvoiceValidationRepository(persisted)

    result = await handler(unit_of_work)(ValidateInvoice(RUN_ID))

    assert result == InvoiceValidated(RUN_ID, InvoiceValidationDecision.AUTO_APPROVE, replayed=True)
    assert unit_of_work.commit_count == 0


@pytest.mark.anyio
async def test_requires_a_persisted_invoice_extraction() -> None:
    unit_of_work = RecordingUnitOfWork()
    unit_of_work.invoice_extractions.value = None

    with pytest.raises(InvoiceValidationRequiresExtraction):
        await handler(unit_of_work)(ValidateInvoice(RUN_ID))
