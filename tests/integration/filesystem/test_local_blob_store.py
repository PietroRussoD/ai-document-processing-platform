"""Local blob storage integration tests."""

import asyncio
import hashlib
import stat
from pathlib import Path

import pytest

from document_platform.adapters.outbound.filesystem import LocalBlobStore
from document_platform.application.ports import BlobIntegrityConflict, BlobTooLarge, EmptyBlob


def _source(tmp_path: Path, content: bytes) -> Path:
    path = tmp_path / "source.pdf"
    path.write_bytes(content)
    return path


@pytest.mark.anyio
async def test_stores_streamed_content_under_its_digest(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path, max_bytes=1024)
    content = b"synthetic invoice"
    expected_digest = hashlib.sha256(content).hexdigest()

    stored = await store.store(_source(tmp_path, content))

    assert stored.content_sha256 == expected_digest
    assert stored.size_bytes == len(content)
    assert stored.key == f"blobs/sha256/{expected_digest[:2]}/{expected_digest}"
    stored_path = tmp_path / stored.key
    assert stored_path.read_bytes() == content
    assert stat.S_IMODE(stored_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(tmp_path.joinpath("blobs").stat().st_mode) == 0o700
    assert stat.S_IMODE(stored_path.parent.stat().st_mode) == 0o700
    assert list((tmp_path / "temporary").iterdir()) == []


@pytest.mark.anyio
async def test_concurrent_identical_content_converges_on_one_blob(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path, max_bytes=1024)
    content = b"same immutable content"

    first, second = await asyncio.gather(
        store.store(_source(tmp_path, content)),
        store.store(tmp_path / "source.pdf"),
    )

    assert first == second
    assert len(list((tmp_path / "blobs").rglob(first.content_sha256))) == 1
    assert list((tmp_path / "temporary").iterdir()) == []


@pytest.mark.anyio
async def test_rejects_empty_content_and_removes_temporary_file(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path, max_bytes=1024)

    with pytest.raises(EmptyBlob):
        await store.store(_source(tmp_path, b""))

    assert list((tmp_path / "temporary").iterdir()) == []
    assert not (tmp_path / "blobs").exists()


@pytest.mark.anyio
async def test_rejects_oversized_content_and_removes_temporary_file(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path, max_bytes=5)

    with pytest.raises(BlobTooLarge, match="5-byte limit"):
        await store.store(_source(tmp_path, b"123456"))

    assert list((tmp_path / "temporary").iterdir()) == []
    assert not (tmp_path / "blobs").exists()


@pytest.mark.anyio
async def test_rejects_an_existing_blob_with_invalid_content(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path, max_bytes=1024)
    content = b"expected content"
    digest = hashlib.sha256(content).hexdigest()
    destination = tmp_path / "blobs" / "sha256" / digest[:2] / digest
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"corrupt-content")

    with pytest.raises(BlobIntegrityConflict):
        await store.store(_source(tmp_path, content))

    assert destination.read_bytes() == b"corrupt-content"
    assert list((tmp_path / "temporary").iterdir()) == []


def test_rejects_a_non_positive_size_limit(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="max_bytes must be positive"):
        LocalBlobStore(tmp_path, max_bytes=0)
