"""Filesystem safety primitives shared by local adapters."""

import os
from contextlib import suppress
from pathlib import Path


def create_private_directory(path: Path) -> None:
    missing_directories: list[Path] = []
    current = path
    while not current.exists():
        missing_directories.append(current)
        current = current.parent

    for directory in reversed(missing_directories):
        with suppress(FileExistsError):
            directory.mkdir(mode=0o700)


def private_file_opener(path: str, flags: int) -> int:
    return os.open(path, flags, 0o600)


def sync_file(path: Path) -> None:
    with path.open("rb") as stored_file:
        os.fsync(stored_file.fileno())


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
