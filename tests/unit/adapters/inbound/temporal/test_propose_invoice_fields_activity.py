"""Temporal advisory invoice proposal activity tests."""

import asyncio
from uuid import UUID

import pytest
from temporalio.exceptions import ApplicationError

from document_platform.adapters.inbound.temporal import ProposeInvoiceFieldsActivity
from document_platform.application.commands import ProposeInvoiceFields
from document_platform.application.ports import InvoiceProposalGenerationFailed
from document_platform.domain.processing import InvoiceProposalGenerationFailureCode

RUN_ID = UUID("a7a7a7a7-a7a7-47a7-87a7-a7a7a7a7a7a7")


class RecordingProposeInvoiceFields:
    def __init__(self) -> None:
        self.commands: list[ProposeInvoiceFields] = []
        self.beginnings: list[tuple[ProposeInvoiceFields, bool]] = []

    async def begin_execution(self, command: ProposeInvoiceFields, *, enabled: bool) -> bool:
        self.beginnings.append((command, enabled))
        return enabled

    async def __call__(self, command: ProposeInvoiceFields) -> None:
        self.commands.append(command)


@pytest.mark.anyio
async def test_maps_run_id_without_returning_proposal_to_temporal() -> None:
    handler = RecordingProposeInvoiceFields()
    activity = ProposeInvoiceFieldsActivity(handler)  # type: ignore[arg-type]

    result = await activity.propose_invoice_fields(str(RUN_ID))

    assert handler.commands == [ProposeInvoiceFields(RUN_ID)]
    assert handler.beginnings == [(ProposeInvoiceFields(RUN_ID), True)]
    assert result is None


@pytest.mark.anyio
async def test_skips_model_when_disabled() -> None:
    handler = RecordingProposeInvoiceFields()
    activity = ProposeInvoiceFieldsActivity(handler, enabled=False)  # type: ignore[arg-type]

    await activity.propose_invoice_fields(str(RUN_ID))

    assert handler.commands == []
    assert handler.beginnings == [(ProposeInvoiceFields(RUN_ID), False)]


class FailingProposeInvoiceFields:
    def __init__(self, code: InvoiceProposalGenerationFailureCode) -> None:
        self.code = code

    async def begin_execution(self, command: ProposeInvoiceFields, *, enabled: bool) -> bool:
        return enabled

    async def __call__(self, command: ProposeInvoiceFields) -> None:
        raise InvoiceProposalGenerationFailed(self.code)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("code", "non_retryable"),
    [
        (InvoiceProposalGenerationFailureCode.TIMEOUT, False),
        (InvoiceProposalGenerationFailureCode.UNAVAILABLE, False),
        (InvoiceProposalGenerationFailureCode.INVALID_RESPONSE, True),
    ],
)
async def test_maps_provider_failure_to_safe_temporal_type(
    code: InvoiceProposalGenerationFailureCode,
    non_retryable: bool,
) -> None:
    activity = ProposeInvoiceFieldsActivity(
        FailingProposeInvoiceFields(code),  # type: ignore[arg-type]
    )

    with pytest.raises(ApplicationError) as error:
        await activity.propose_invoice_fields(str(RUN_ID))

    assert error.value.type == f"INVOICE_PROPOSAL_{code.value}"
    assert error.value.non_retryable is non_retryable


def test_rejects_an_unbounded_model_concurrency_setting() -> None:
    with pytest.raises(ValueError, match="positive"):
        ProposeInvoiceFieldsActivity(
            RecordingProposeInvoiceFields(),  # type: ignore[arg-type]
            max_concurrent_requests=0,
        )


@pytest.mark.anyio
async def test_limits_simultaneous_model_calls_per_worker() -> None:
    first_started = asyncio.Event()
    release_first = asyncio.Event()

    class BlockingProposeInvoiceFields:
        active = 0
        max_active = 0
        begun = 0

        async def begin_execution(self, command: ProposeInvoiceFields, *, enabled: bool) -> bool:
            self.begun += 1
            return enabled

        async def __call__(self, command: ProposeInvoiceFields) -> None:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            if not first_started.is_set():
                first_started.set()
                await release_first.wait()
            self.active -= 1

    handler = BlockingProposeInvoiceFields()
    activity = ProposeInvoiceFieldsActivity(handler, max_concurrent_requests=1)  # type: ignore[arg-type]
    first = asyncio.create_task(activity.propose_invoice_fields(str(RUN_ID)))
    await first_started.wait()
    second = asyncio.create_task(activity.propose_invoice_fields(str(RUN_ID)))
    await asyncio.sleep(0)
    assert handler.begun == 2
    assert handler.active == 1
    release_first.set()
    await asyncio.gather(first, second)

    assert handler.max_active == 1
