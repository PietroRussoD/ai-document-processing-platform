"""Content-addressed local blob storage."""

import hashlib
import os
import re
from pathlib import Path
from uuid import uuid4

import anyio

from document_platform.adapters.filesystem_safety import (
    create_private_directory,
    private_file_opener,
    sync_directory,
    sync_file,
)
from document_platform.application.ports import (
    BlobIntegrityConflict,
    BlobNotFound,
    BlobTooLarge,
    EmptyBlob,
    StoredBlob,
)


class LocalBlobStore:
    def __init__(self, root: Path, max_bytes: int) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self._root = root
        self._max_bytes = max_bytes

    async def store(self, source: Path) -> StoredBlob:
        temporary_directory = self._root / "temporary"
        temporary_path = temporary_directory / f"{uuid4()}.upload"
        await anyio.to_thread.run_sync(create_private_directory, temporary_directory)

        digest = hashlib.sha256()
        size_bytes = 0

        try:
            async with await anyio.open_file(
                temporary_path,
                "xb",
                opener=private_file_opener,
            ) as temporary_file:
                async with await anyio.open_file(source, "rb") as source_file:
                    while chunk := await source_file.read(64 * 1024):
                        size_bytes += len(chunk)
                        if size_bytes > self._max_bytes:
                            raise BlobTooLarge(self._max_bytes)
                        digest.update(chunk)
                        await temporary_file.write(chunk)
                await temporary_file.flush()

            if size_bytes == 0:
                raise EmptyBlob

            content_sha256 = digest.hexdigest()
            key = f"blobs/sha256/{content_sha256[:2]}/{content_sha256}"
            destination = self._root / key

            await anyio.to_thread.run_sync(sync_file, temporary_path)
            await anyio.to_thread.run_sync(
                _publish,
                temporary_path,
                destination,
                content_sha256,
                size_bytes,
            )
            return StoredBlob(
                key=key,
                content_sha256=content_sha256,
                size_bytes=size_bytes,
            )
        finally:
            await anyio.to_thread.run_sync(temporary_path.unlink, True)

    async def load(self, key: str) -> bytes:
        return await anyio.to_thread.run_sync(_load, self._path_for_key(key), self._max_bytes)

    def _path_for_key(self, key: str) -> Path:
        match = _BLOB_KEY.fullmatch(key)
        if match is None or match.group("prefix") != match.group("digest")[:2]:
            raise BlobNotFound(key)
        return self._root / key


_BLOB_KEY = re.compile(r"blobs/sha256/(?P<prefix>[0-9a-f]{2})/(?P<digest>[0-9a-f]{64})")


def _publish(
    temporary_path: Path,
    destination: Path,
    content_sha256: str,
    size_bytes: int,
) -> None:
    create_private_directory(destination.parent)
    try:
        os.link(temporary_path, destination)
        sync_directory(destination.parent)
    except FileExistsError:
        if not _matches(destination, content_sha256, size_bytes):
            key = destination.relative_to(destination.parents[3]).as_posix()
            raise BlobIntegrityConflict(key) from None


def _matches(path: Path, content_sha256: str, size_bytes: int) -> bool:
    if path.stat().st_size != size_bytes:
        return False

    digest = hashlib.sha256()
    with path.open("rb") as stored_file:
        while chunk := stored_file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest() == content_sha256


def _load(path: Path, max_bytes: int) -> bytes:
    try:
        if path.stat().st_size > max_bytes:
            raise BlobTooLarge(max_bytes)
        return path.read_bytes()
    except FileNotFoundError:
        key = path.relative_to(path.parents[3]).as_posix()
        raise BlobNotFound(key) from None
