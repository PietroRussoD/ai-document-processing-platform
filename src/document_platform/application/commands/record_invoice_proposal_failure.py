"""Persist a terminal provider failure without failing the document."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from document_platform.application.ports import (
    InvoiceProposalFailureAlreadyExists,
    InvoiceProposalOutcomeConflict,
    UnitOfWorkFactory,
)
from document_platform.domain.processing import (
    AiInvoiceProposalFailure,
    InvoiceModelProvider,
    InvoiceProposalGenerationFailureCode,
)


@dataclass(frozen=True, slots=True)
class RecordInvoiceProposalFailure:
    processing_run_id: UUID
    provider: InvoiceModelProvider
    model_reference: str
    code: InvoiceProposalGenerationFailureCode


@dataclass(frozen=True, slots=True)
class InvoiceProposalFailureRecorded:
    failure: AiInvoiceProposalFailure
    replayed: bool


class RecordInvoiceProposalFailureHandler:
    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        clock: Callable[[], datetime],
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def __call__(
        self, command: RecordInvoiceProposalFailure
    ) -> InvoiceProposalFailureRecorded:
        async with self._unit_of_work_factory() as unit_of_work:
            existing = await unit_of_work.invoice_proposal_failures.get(command.processing_run_id)
            if existing is not None:
                return _replayed_or_conflict(command, existing)

        failure = AiInvoiceProposalFailure(
            processing_run_id=command.processing_run_id,
            provider=command.provider,
            model_reference=command.model_reference,
            code=command.code,
            failed_at=self._clock(),
        )
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                await unit_of_work.invoice_proposal_failures.add(failure)
                await unit_of_work.commit()
        except InvoiceProposalFailureAlreadyExists:
            async with self._unit_of_work_factory() as unit_of_work:
                existing = await unit_of_work.invoice_proposal_failures.get(
                    command.processing_run_id
                )
            if existing is not None:
                return _replayed_or_conflict(command, existing)
            raise
        return InvoiceProposalFailureRecorded(failure=failure, replayed=False)


def _replayed_or_conflict(
    command: RecordInvoiceProposalFailure,
    existing: AiInvoiceProposalFailure,
) -> InvoiceProposalFailureRecorded:
    if (
        existing.provider is not command.provider
        or existing.model_reference != command.model_reference
        or existing.code is not command.code
    ):
        raise InvoiceProposalOutcomeConflict(command.processing_run_id)
    return InvoiceProposalFailureRecorded(failure=existing, replayed=True)
