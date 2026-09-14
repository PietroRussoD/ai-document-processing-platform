"""Content-addressed local blob storage."""

import hashlib
import os
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

import anyio

from document_platform.application.ports import (
    BlobIntegrityConflict,
    BlobTooLarge,
    ByteStream,
    EmptyBlob,
    StoredBlob,
)


class LocalBlobStore:
    def __init__(self, root: Path, max_bytes: int) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self._root = root
        self._max_bytes = max_bytes

    async def store(self, content: ByteStream) -> StoredBlob:
        temporary_directory = self._root / "temporary"
        temporary_path = temporary_directory / f"{uuid4()}.upload"
        await anyio.to_thread.run_sync(_create_private_directory, temporary_directory)

        digest = hashlib.sha256()
        size_bytes = 0

        try:
            async with await anyio.open_file(
                temporary_path,
                "xb",
                opener=_private_file_opener,
            ) as temporary_file:
                async for chunk in content:
                    if not chunk:
                        continue
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

            await anyio.to_thread.run_sync(_sync_file, temporary_path)
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


def _create_private_directory(path: Path) -> None:
    missing_directories: list[Path] = []
    current = path
    while not current.exists():
        missing_directories.append(current)
        current = current.parent

    for directory in reversed(missing_directories):
        with suppress(FileExistsError):
            directory.mkdir(mode=0o700)


def _private_file_opener(path: str, flags: int) -> int:
    return os.open(path, flags, 0o600)


def _sync_file(path: Path) -> None:
    with path.open("rb") as stored_file:
        os.fsync(stored_file.fileno())


def _publish(
    temporary_path: Path,
    destination: Path,
    content_sha256: str,
    size_bytes: int,
) -> None:
    _create_private_directory(destination.parent)
    try:
        os.link(temporary_path, destination)
        _sync_directory(destination.parent)
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


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
