"""Validate, store and register a staged PDF upload."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from document_platform.application.commands.register_document import (
    RegisterDocument,
    RegisteredDocument,
)
from document_platform.application.ports import (
    BlobStore,
    BlobTooLarge,
    EmptyBlob,
    PdfInspector,
)
from document_platform.application.upload_idempotency import IdempotencyKey
from document_platform.domain.documents import PDF_MEDIA_TYPE, validate_original_filename

type DocumentRegistrar = Callable[[RegisterDocument], Awaitable[RegisteredDocument]]


class UnsupportedDocumentMediaType(ValueError):
    def __init__(self, media_type: str) -> None:
        super().__init__(f"unsupported document media type: {media_type}")


class InvalidStagedUpload(ValueError):
    """Raised when the upload source is not a regular request-owned file."""


@dataclass(frozen=True, slots=True)
class AcceptDocumentUpload:
    idempotency_key: str
    original_filename: str
    declared_media_type: str
    staged_path: Path


class AcceptDocumentUploadHandler:
    def __init__(
        self,
        *,
        pdf_inspector: PdfInspector,
        blob_store: BlobStore,
        register_document: DocumentRegistrar,
        max_bytes: int,
    ) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self._pdf_inspector = pdf_inspector
        self._blob_store = blob_store
        self._register_document = register_document
        self._max_bytes = max_bytes

    async def __call__(self, command: AcceptDocumentUpload) -> RegisteredDocument:
        validate_upload_metadata(
            idempotency_key=command.idempotency_key,
            original_filename=command.original_filename,
            declared_media_type=command.declared_media_type,
        )

        size_bytes = self._validated_size(command.staged_path)
        inspection = await self._pdf_inspector.inspect(command.staged_path)
        stored_blob = await self._blob_store.store(command.staged_path)

        if stored_blob.size_bytes != size_bytes:
            raise InvalidStagedUpload("staged upload changed while it was being accepted")

        return await self._register_document(
            RegisterDocument(
                idempotency_key=command.idempotency_key,
                original_filename=command.original_filename,
                size_bytes=stored_blob.size_bytes,
                page_count=inspection.page_count,
                content_sha256=stored_blob.content_sha256,
                storage_key=stored_blob.key,
            )
        )

    def _validated_size(self, path: Path) -> int:
        if path.is_symlink() or not path.is_file():
            raise InvalidStagedUpload("staged upload must be a regular file")

        size_bytes = path.stat().st_size
        if size_bytes == 0:
            raise EmptyBlob
        if size_bytes > self._max_bytes:
            raise BlobTooLarge(self._max_bytes)
        return size_bytes


def validate_upload_metadata(
    *,
    idempotency_key: str,
    original_filename: str,
    declared_media_type: str,
) -> None:
    IdempotencyKey(idempotency_key)
    validate_original_filename(original_filename)
    if declared_media_type != PDF_MEDIA_TYPE:
        raise UnsupportedDocumentMediaType(declared_media_type)
