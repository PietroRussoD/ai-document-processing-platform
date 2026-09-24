"""Read-only local storage inventory tests."""

from pathlib import Path

import pytest

from document_platform.adapters.outbound.filesystem import LocalBlobStore, LocalStorageInventory


@pytest.mark.anyio
async def test_counts_published_and_in_progress_files_without_reading_them(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"synthetic invoice")
    stored = await LocalBlobStore(tmp_path, max_bytes=1_024).store(source)
    (tmp_path / "temporary" / "pending.upload").write_bytes(b"pending")
    (tmp_path / "incoming").mkdir()
    (tmp_path / "incoming" / "request.upload").write_bytes(b"request")
    (tmp_path / "temporary" / "other.txt").write_bytes(b"ignored")

    snapshot = LocalStorageInventory(tmp_path).scan()

    assert len(snapshot.published_blobs) == 1
    assert snapshot.published_blobs[0].key == stored.key
    assert snapshot.published_blobs[0].content_sha256 == stored.content_sha256
    assert snapshot.published_blobs[0].size_bytes == stored.size_bytes
    assert snapshot.temporary_uploads == 1
    assert snapshot.incoming_uploads == 1
    assert snapshot.unrecognized_entries == 1
    assert snapshot.scanned_entries == 5
    assert not snapshot.truncated


@pytest.mark.anyio
async def test_limits_scan_and_does_not_follow_blob_symlinks(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"published")
    stored = await LocalBlobStore(tmp_path, max_bytes=1_024).store(source)
    blob_path = tmp_path / stored.key
    link_path = blob_path.parent / ("f" * 64)
    link_path.symlink_to(blob_path)

    inventory = LocalStorageInventory(tmp_path)
    complete = inventory.scan()
    limited = inventory.scan(limit=1)

    assert [entry.key for entry in complete.published_blobs] == [stored.key]
    assert complete.unrecognized_entries == 1
    assert not complete.truncated
    assert limited.scanned_entries == 1
    assert limited.truncated


def test_rejects_a_symlinked_storage_directory(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "data"
    root.mkdir()
    (root / "blobs").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="not a regular directory"):
        LocalStorageInventory(root).scan()


def test_rejects_a_non_positive_limit(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="limit must be positive"):
        LocalStorageInventory(tmp_path).scan(limit=0)
