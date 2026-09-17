"""Validate a persisted invoice extraction with deterministic business rules."""

from dataclasses import dataclass
from uuid import UUID

from document_platform.application.ports import (
    Clock,
    InvoiceValidationAlreadyExists,
    UnitOfWorkFactory,
)
from document_platform.domain.processing import (
    InvoiceValidationDecision,
    InvoiceValidationPolicy,
)


@dataclass(frozen=True, slots=True)
class ValidateInvoice:
    processing_run_id: UUID


@dataclass(frozen=True, slots=True)
class InvoiceValidated:
    processing_run_id: UUID
    decision: InvoiceValidationDecision
    replayed: bool


class InvoiceValidationRequiresExtraction(RuntimeError):
    def __init__(self, processing_run_id: UUID) -> None:
        super().__init__(f"invoice extraction is missing: {processing_run_id}")


class ValidateInvoiceHandler:
    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        validation_policy: InvoiceValidationPolicy,
        clock: Clock,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._validation_policy = validation_policy
        self._clock = clock

    async def __call__(self, command: ValidateInvoice) -> InvoiceValidated:
        async with self._unit_of_work_factory() as unit_of_work:
            existing = await unit_of_work.invoice_validations.get(command.processing_run_id)
            if existing is not None:
                return InvoiceValidated(
                    processing_run_id=existing.processing_run_id,
                    decision=existing.decision,
                    replayed=True,
                )

            extraction = await unit_of_work.invoice_extractions.get(command.processing_run_id)
            if extraction is None:
                raise InvoiceValidationRequiresExtraction(command.processing_run_id)

            validation = self._validation_policy.validate(
                extraction=extraction,
                validated_at=self._clock(),
            )
            try:
                await unit_of_work.invoice_validations.add(validation)
                await unit_of_work.commit()
            except InvoiceValidationAlreadyExists:
                return InvoiceValidated(
                    processing_run_id=validation.processing_run_id,
                    decision=validation.decision,
                    replayed=True,
                )
            return InvoiceValidated(
                processing_run_id=validation.processing_run_id,
                decision=validation.decision,
                replayed=False,
            )
