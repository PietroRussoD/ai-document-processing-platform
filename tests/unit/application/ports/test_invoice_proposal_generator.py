"""Bounded model-proposal port tests using an in-memory fake."""

from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

import pytest

from document_platform.application.ports import (
    MAX_SELECTED_TEXT_CHARACTERS,
    InvalidInvoiceProposalRequest,
    InvoiceProposalGenerator,
    InvoiceProposalInputTooLarge,
    InvoiceProposalRequest,
)
from document_platform.domain.processing import (
    AiInvoiceExtractionProposal,
    InvoiceModelProvider,
    InvoiceProposalStatus,
)

RUN_ID = UUID("f6f6f6f6-f6f6-46f6-86f6-f6f6f6f6f6f6")
AT = datetime(2026, 9, 27, 13, 0, tzinfo=UTC)


class FakeInvoiceProposalGenerator:
    def __init__(self, proposal: AiInvoiceExtractionProposal) -> None:
        self._proposal = proposal
        self.requests: list[InvoiceProposalRequest] = []

    async def generate(self, request: InvoiceProposalRequest) -> AiInvoiceExtractionProposal:
        self.requests.append(request)
        return self._proposal


def build_proposal(request: InvoiceProposalRequest) -> AiInvoiceExtractionProposal:
    return AiInvoiceExtractionProposal(
        processing_run_id=request.processing_run_id,
        schema_version=1,
        provider=InvoiceModelProvider.OLLAMA,
        model_reference="fake-model",
        model_digest=None,
        prompt_version="invoice-fields-v1",
        selected_text_sha256=request.selected_text_sha256,
        status=InvoiceProposalStatus.VALID,
        invoice_number="INV-42",
        issue_date=date(2026, 9, 27),
        supplier_name="Example Supplier Ltd",
        currency="EUR",
        total_amount=Decimal("125.50"),
        issues=(),
        proposed_at=AT,
    )


def test_request_hashes_exact_selected_text_without_normalizing_it() -> None:
    text = "  INVOICE\nInvoice number: INV-42\n"
    request = InvoiceProposalRequest(processing_run_id=RUN_ID, selected_text=text)

    assert request.selected_text == text
    assert request.selected_text_sha256 == sha256(text.encode("utf-8")).hexdigest()


@pytest.mark.parametrize(
    ("processing_run_id", "selected_text"),
    [(UUID(int=0), "invoice"), (RUN_ID, " \n ")],
)
def test_rejects_nil_run_id_or_blank_selected_text(
    processing_run_id: UUID,
    selected_text: str,
) -> None:
    with pytest.raises(InvalidInvoiceProposalRequest):
        InvoiceProposalRequest(processing_run_id=processing_run_id, selected_text=selected_text)


def test_rejects_selected_text_over_the_model_input_limit() -> None:
    with pytest.raises(InvoiceProposalInputTooLarge) as error:
        InvoiceProposalRequest(
            processing_run_id=RUN_ID,
            selected_text="x" * (MAX_SELECTED_TEXT_CHARACTERS + 1),
        )

    assert error.value.max_characters == MAX_SELECTED_TEXT_CHARACTERS


@pytest.mark.anyio
async def test_generator_port_can_be_driven_by_a_fake_without_ollama() -> None:
    request = InvoiceProposalRequest(processing_run_id=RUN_ID, selected_text="INVOICE INV-42")
    expected = build_proposal(request)
    fake = FakeInvoiceProposalGenerator(expected)
    generator: InvoiceProposalGenerator = fake

    actual = await generator.generate(request)

    assert actual is expected
    assert fake.requests == [request]


def test_request_is_immutable() -> None:
    request = InvoiceProposalRequest(processing_run_id=RUN_ID, selected_text="invoice")

    with pytest.raises(FrozenInstanceError):
        request.selected_text = "changed"  # type: ignore[misc]
