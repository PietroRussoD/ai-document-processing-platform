"""Document lifecycle unit tests."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from document_platform.domain.documents import (
    Document,
    DocumentStatus,
    InvalidDocument,
    InvalidDocumentTransition,
)

DOCUMENT_ID = UUID("d13d7954-7051-4ccd-90b3-e97c83e52e56")
ACCEPTED_AT = datetime(2026, 9, 13, 8, 0, tzinfo=UTC)


def accepted_document(**overrides: object) -> Document:
    values: dict[str, object] = {
        "document_id": DOCUMENT_ID,
        "original_filename": "supplier-invoice.pdf",
        "size_bytes": 42_000,
        "page_count": 2,
        "content_sha256": "a" * 64,
        "storage_key": "blobs/sha256/aa/" + "a" * 64,
        "accepted_at": ACCEPTED_AT,
    }
    values.update(overrides)
    return Document.accept_pdf(**values)  # type: ignore[arg-type]


def test_accepts_a_valid_pdf() -> None:
    document = accepted_document()

    assert document.id == DOCUMENT_ID
    assert document.media_type == "application/pdf"
    assert document.status is DocumentStatus.UPLOADED
    assert document.status_changed_at == ACCEPTED_AT
    assert document.version == 0


def test_accepts_a_pdf_with_unknown_page_count() -> None:
    document = accepted_document(page_count=None)

    assert document.page_count is None


def test_records_page_count_without_changing_document_status_time() -> None:
    document = accepted_document(page_count=None)

    updated = document.record_page_count(2)

    assert updated.page_count == 2
    assert updated.version == document.version + 1
    assert updated.status_changed_at == document.status_changed_at


def test_rejects_a_page_count_that_changes_after_it_is_known() -> None:
    document = accepted_document(page_count=2)

    with pytest.raises(InvalidDocument, match="does not match"):
        document.record_page_count(3)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("document_id", UUID(int=0)),
        ("original_filename", " "),
        ("original_filename", "../invoice.pdf"),
        ("original_filename", "folder\\invoice.pdf"),
        ("size_bytes", 0),
        ("page_count", 0),
        ("content_sha256", "A" * 64),
        ("content_sha256", "abc"),
        ("storage_key", " "),
        ("accepted_at", datetime(2026, 9, 13, 8, 0)),
    ],
)
def test_rejects_invalid_document_metadata(field: str, invalid_value: object) -> None:
    with pytest.raises(InvalidDocument):
        accepted_document(**{field: invalid_value})


def test_completes_automatic_processing() -> None:
    processing_at = ACCEPTED_AT + timedelta(seconds=1)
    approved_at = processing_at + timedelta(seconds=2)

    uploaded = accepted_document()
    processing = uploaded.start_processing(at=processing_at)
    approved = processing.approve(at=approved_at)

    assert uploaded.status is DocumentStatus.UPLOADED
    assert processing.status is DocumentStatus.PROCESSING
    assert processing.version == 1
    assert approved.status is DocumentStatus.APPROVED
    assert approved.status_changed_at == approved_at
    assert approved.version == 2


@pytest.mark.parametrize("final_status", [DocumentStatus.APPROVED, DocumentStatus.REJECTED])
def test_completes_human_review(final_status: DocumentStatus) -> None:
    document = (
        accepted_document()
        .start_processing(at=ACCEPTED_AT + timedelta(seconds=1))
        .require_review(at=ACCEPTED_AT + timedelta(seconds=2))
    )

    completed = (
        document.approve(at=ACCEPTED_AT + timedelta(seconds=3))
        if final_status is DocumentStatus.APPROVED
        else document.reject(at=ACCEPTED_AT + timedelta(seconds=3))
    )

    assert completed.status is final_status
    assert completed.version == 3


@pytest.mark.parametrize("final_status", [DocumentStatus.APPROVED, DocumentStatus.REJECTED])
def test_reopens_a_terminal_document_for_reprocessing(final_status: DocumentStatus) -> None:
    resolved = (
        accepted_document()
        .start_processing(at=ACCEPTED_AT + timedelta(seconds=1))
        .require_review(at=ACCEPTED_AT + timedelta(seconds=2))
    )
    resolved = (
        resolved.approve(at=ACCEPTED_AT + timedelta(seconds=3))
        if final_status is DocumentStatus.APPROVED
        else resolved.reject(at=ACCEPTED_AT + timedelta(seconds=3))
    )

    reopened_at = ACCEPTED_AT + timedelta(seconds=4)
    reopened = resolved.reopen_for_reprocessing(at=reopened_at)

    assert reopened.status is DocumentStatus.PROCESSING
    assert reopened.status_changed_at == reopened_at
    assert reopened.version == 4


def test_reopens_a_failed_document_for_reprocessing() -> None:
    failed = (
        accepted_document()
        .start_processing(at=ACCEPTED_AT + timedelta(seconds=1))
        .fail(at=ACCEPTED_AT + timedelta(seconds=2))
    )

    reopened = failed.reopen_for_reprocessing(at=ACCEPTED_AT + timedelta(seconds=3))

    assert reopened.status is DocumentStatus.PROCESSING
    assert reopened.version == 3


def test_marks_an_unrecognized_document_as_unsupported() -> None:
    processing = accepted_document().start_processing(at=ACCEPTED_AT + timedelta(seconds=1))
    unsupported_at = ACCEPTED_AT + timedelta(seconds=2)

    unsupported = processing.mark_unsupported(at=unsupported_at)

    assert unsupported.status is DocumentStatus.UNSUPPORTED
    assert unsupported.status_changed_at == unsupported_at
    with pytest.raises(InvalidDocumentTransition, match="cannot reopen for reprocessing"):
        unsupported.reopen_for_reprocessing(at=ACCEPTED_AT + timedelta(seconds=3))


@pytest.mark.parametrize("status", [DocumentStatus.UPLOADED, DocumentStatus.PROCESSING])
def test_rejects_reprocessing_for_a_nonterminal_document(status: DocumentStatus) -> None:
    document = accepted_document()
    if status is DocumentStatus.PROCESSING:
        document = document.start_processing(at=ACCEPTED_AT + timedelta(seconds=1))

    with pytest.raises(
        InvalidDocumentTransition,
        match=f"cannot reopen for reprocessing from {status}",
    ):
        document.reopen_for_reprocessing(at=ACCEPTED_AT + timedelta(seconds=2))


def test_rejects_a_transition_that_skips_processing() -> None:
    with pytest.raises(
        InvalidDocumentTransition,
        match="cannot transition from UPLOADED to APPROVED",
    ):
        accepted_document().approve(at=ACCEPTED_AT + timedelta(seconds=1))


def test_rejects_a_transition_with_a_backwards_timestamp() -> None:
    document = accepted_document().start_processing(at=ACCEPTED_AT + timedelta(seconds=2))

    with pytest.raises(InvalidDocumentTransition, match="must not move backwards"):
        document.require_review(at=ACCEPTED_AT + timedelta(seconds=1))
