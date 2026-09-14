"""Bounded request-file staging."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import anyio
from fastapi import UploadFile

from document_platform.adapters.filesystem_safety import (
    create_private_directory,
    private_file_opener,
    sync_file,
)
from document_platform.application.ports import BlobTooLarge, EmptyBlob

CHUNK_SIZE = 64 * 1024


@asynccontextmanager
async def stage_upload(
    upload: UploadFile,
    *,
    storage_root: Path,
    max_bytes: int,
) -> AsyncGenerator[Path]:
    incoming_directory = storage_root / "incoming"
    staged_path = incoming_directory / f"{uuid4()}.upload"
    await anyio.to_thread.run_sync(create_private_directory, incoming_directory)
    size_bytes = 0

    try:
        async with await anyio.open_file(
            staged_path,
            "xb",
            opener=private_file_opener,
        ) as staged_file:
            while chunk := await upload.read(CHUNK_SIZE):
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    raise BlobTooLarge(max_bytes)
                await staged_file.write(chunk)
            await staged_file.flush()

        if size_bytes == 0:
            raise EmptyBlob

        await anyio.to_thread.run_sync(sync_file, staged_path)
        yield staged_path
    finally:
        await upload.close()
        await anyio.to_thread.run_sync(staged_path.unlink, True)
