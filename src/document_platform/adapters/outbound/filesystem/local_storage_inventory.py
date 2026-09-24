"""Bounded, read-only inventory of local blob storage."""

import os
import re
import stat
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

_PREFIX = re.compile(r"[0-9a-f]{2}")
_DIGEST = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class PublishedBlobEntry:
    key: str
    content_sha256: str
    size_bytes: int
    modified_at: datetime


@dataclass(frozen=True, slots=True)
class StagedUploadEntry:
    location: Literal["temporary", "incoming"]
    size_bytes: int
    modified_at: datetime


@dataclass(frozen=True, slots=True)
class LocalStorageInventorySnapshot:
    published_blobs: tuple[PublishedBlobEntry, ...]
    staged_uploads: tuple[StagedUploadEntry, ...]
    unrecognized_entries: int
    scanned_entries: int
    truncated: bool

    @property
    def temporary_uploads(self) -> int:
        return sum(upload.location == "temporary" for upload in self.staged_uploads)

    @property
    def incoming_uploads(self) -> int:
        return sum(upload.location == "incoming" for upload in self.staged_uploads)


class LocalStorageInventory:
    def __init__(self, root: Path) -> None:
        self._root = root

    def scan(self, *, limit: int = 1_000) -> LocalStorageInventorySnapshot:
        if limit < 1:
            raise ValueError("limit must be positive")

        published_blobs: list[PublishedBlobEntry] = []
        staged_uploads: list[StagedUploadEntry] = []
        unrecognized_entries = 0
        scanned_entries = 0
        truncated = False

        def take_entry() -> bool:
            nonlocal scanned_entries, truncated
            if scanned_entries == limit:
                truncated = True
                return False
            scanned_entries += 1
            return True

        def snapshot() -> LocalStorageInventorySnapshot:
            return LocalStorageInventorySnapshot(
                published_blobs=tuple(published_blobs),
                staged_uploads=tuple(staged_uploads),
                unrecognized_entries=unrecognized_entries,
                scanned_entries=scanned_entries,
                truncated=truncated,
            )

        _check_directory(self._root)
        _check_directory(self._root / "blobs")
        blob_directory = self._root / "blobs" / "sha256"
        for prefix in _directory_entries(blob_directory):
            if not take_entry():
                return snapshot()
            if not _PREFIX.fullmatch(prefix.name) or not prefix.is_dir(follow_symlinks=False):
                unrecognized_entries += 1
                continue
            for blob in _directory_entries(Path(prefix.path)):
                if not take_entry():
                    return snapshot()
                if (
                    not _DIGEST.fullmatch(blob.name)
                    or not blob.name.startswith(prefix.name)
                    or not blob.is_file(follow_symlinks=False)
                ):
                    unrecognized_entries += 1
                    continue
                metadata = blob.stat(follow_symlinks=False)
                published_blobs.append(
                    PublishedBlobEntry(
                        key=f"blobs/sha256/{prefix.name}/{blob.name}",
                        content_sha256=blob.name,
                        size_bytes=metadata.st_size,
                        modified_at=datetime.fromtimestamp(metadata.st_mtime, tz=UTC),
                    )
                )

        for directory_name in ("temporary", "incoming"):
            for entry in _directory_entries(self._root / directory_name):
                if not take_entry():
                    return snapshot()
                if not entry.name.endswith(".upload") or not entry.is_file(follow_symlinks=False):
                    unrecognized_entries += 1
                    continue
                metadata = entry.stat(follow_symlinks=False)
                staged_uploads.append(
                    StagedUploadEntry(
                        location=directory_name,
                        size_bytes=metadata.st_size,
                        modified_at=datetime.fromtimestamp(metadata.st_mtime, tz=UTC),
                    )
                )

        return snapshot()


def _check_directory(path: Path) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return
    if not stat.S_ISDIR(mode):
        raise ValueError(f"storage inventory directory is not a regular directory: {path}")


def _directory_entries(path: Path) -> Iterator[os.DirEntry[str]]:
    _check_directory(path)
    if not path.exists():
        return
    with os.scandir(path) as entries:
        yield from entries
