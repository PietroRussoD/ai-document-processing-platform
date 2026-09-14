"""Document-upload acceptance orchestration tests."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from document_platform.application.commands import (
    AcceptDocumentUpload,
    AcceptDocumentUploadHandler,
    InvalidStagedUpload,
    RegisterDocument,
    RegisteredDocument,
    UnsupportedDocumentMediaType,
)
from document_platform.application.ports import (
    BlobTooLarge,
    EmptyBlob,
    InvalidPdf,
    PdfInspection,
    StoredBlob,
)

ACCEPTED_AT = datetime(2026, 9, 14, 15, 0, tzinfo=UTC)


class RecordingPdfInspector:
    def __init__(self, events: list[str], *, error: Exception | None = None) -> None:
        self._events = events
        self._error = error

    async def inspect(self, path: Path) -> PdfInspection:
        self._events.append(f"inspect:{path.name}")
        if self._error is not None:
            raise self._error
        return PdfInspection(page_count=2)


class RecordingBlobStore:
    def __init__(self, events: list[str], *, size_bytes: int) -> None:
        self._events = events
        self._size_bytes = size_bytes

    async def store(self, source: Path) -> StoredBlob:
        self._events.append(f"store:{source.name}")
        return StoredBlob(
            key="blobs/sha256/aa/" + "a" * 64,
            content_sha256="a" * 64,
            size_bytes=self._size_bytes,
        )


def staged_upload(path: Path, **overrides: object) -> AcceptDocumentUpload:
    values: dict[str, object] = {
        "idempotency_key": "request-42",
        "original_filename": "supplier-invoice.pdf",
        "declared_media_type": "application/pdf",
        "staged_path": path,
    }
    values.update(overrides)
    return AcceptDocumentUpload(**values)  # type: ignore[arg-type]


def handler(
    events: list[str],
    *,
    source_size: int,
    inspector_error: Exception | None = None,
) -> tuple[AcceptDocumentUploadHandler, list[RegisterDocument]]:
    registrations: list[RegisterDocument] = []

    async def register(command: RegisterDocument) -> RegisteredDocument:
        events.append("register")
        registrations.append(command)
        return RegisteredDocument(
            document_id=UUID("c1e87668-329b-4862-87fc-e4f5150e233c"),
            processing_run_id=UUID("91c5567b-8951-4713-b9c6-211055d4bb3e"),
            accepted_at=ACCEPTED_AT,
            replayed=False,
        )

    return (
        AcceptDocumentUploadHandler(
            pdf_inspector=RecordingPdfInspector(events, error=inspector_error),
            blob_store=RecordingBlobStore(events, size_bytes=source_size),
            register_document=register,
            max_bytes=1024,
        ),
        registrations,
    )


@pytest.mark.anyio
async def test_validates_stores_and_registers_a_staged_pdf(tmp_path: Path) -> None:
    source = tmp_path / "staged-upload"
    source.write_bytes(b"valid staged bytes")
    events: list[str] = []
    accept, registrations = handler(events, source_size=source.stat().st_size)

    result = await accept(staged_upload(source))

    assert result.replayed is False
    assert events == ["inspect:staged-upload", "store:staged-upload", "register"]
    assert registrations == [
        RegisterDocument(
            idempotency_key="request-42",
            original_filename="supplier-invoice.pdf",
            size_bytes=len(b"valid staged bytes"),
            page_count=2,
            content_sha256="a" * 64,
            storage_key="blobs/sha256/aa/" + "a" * 64,
        )
    ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"declared_media_type": "text/plain"}, UnsupportedDocumentMediaType),
        ({"original_filename": "../invoice.pdf"}, ValueError),
        ({"idempotency_key": " "}, ValueError),
    ],
)
async def test_rejects_invalid_metadata_before_inspection(
    tmp_path: Path,
    overrides: dict[str, object],
    error: type[Exception],
) -> None:
    source = tmp_path / "staged-upload"
    source.write_bytes(b"content")
    events: list[str] = []
    accept, _ = handler(events, source_size=source.stat().st_size)

    with pytest.raises(error):
        await accept(staged_upload(source, **overrides))

    assert events == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("content", "error"),
    [(b"", EmptyBlob), (b"a" * 1025, BlobTooLarge)],
)
async def test_rejects_an_invalid_size_before_parsing(
    tmp_path: Path,
    content: bytes,
    error: type[Exception],
) -> None:
    source = tmp_path / "staged-upload"
    source.write_bytes(content)
    events: list[str] = []
    accept, _ = handler(events, source_size=len(content))

    with pytest.raises(error):
        await accept(staged_upload(source))

    assert events == []


@pytest.mark.anyio
async def test_does_not_store_a_pdf_rejected_by_the_inspector(tmp_path: Path) -> None:
    source = tmp_path / "staged-upload"
    source.write_bytes(b"invalid PDF")
    events: list[str] = []
    accept, _ = handler(
        events,
        source_size=source.stat().st_size,
        inspector_error=InvalidPdf("invalid PDF"),
    )

    with pytest.raises(InvalidPdf):
        await accept(staged_upload(source))

    assert events == ["inspect:staged-upload"]


@pytest.mark.anyio
async def test_rejects_a_source_that_changes_during_acceptance(tmp_path: Path) -> None:
    source = tmp_path / "staged-upload"
    source.write_bytes(b"original content")
    events: list[str] = []
    accept, _ = handler(events, source_size=1)

    with pytest.raises(InvalidStagedUpload, match="changed"):
        await accept(staged_upload(source))

    assert events == ["inspect:staged-upload", "store:staged-upload"]


def test_rejects_a_non_positive_size_limit() -> None:
    with pytest.raises(ValueError, match="max_bytes must be positive"):
        AcceptDocumentUploadHandler(
            pdf_inspector=RecordingPdfInspector([]),
            blob_store=RecordingBlobStore([], size_bytes=1),
            register_document=lambda command: pytest.fail(str(command)),
            max_bytes=0,
        )
