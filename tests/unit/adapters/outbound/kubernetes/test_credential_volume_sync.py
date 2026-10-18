"""Tests for secure credential delivery into the worker volume."""

import os
import stat
from pathlib import Path

import pytest

from document_platform.credential_volume_sync import (
    CredentialSyncError,
    check_target,
    sync_once,
    sync_or_remove,
)

_CA = b"-----BEGIN CERTIFICATE-----\nsynthetic-ca\n-----END CERTIFICATE-----\n"


@pytest.fixture
def credentials(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir(mode=0o700)
    (source / "ca.pem").write_bytes(_CA)
    (source / "ca.pem").chmod(0o600)
    (source / "token").write_text("synthetic-token", encoding="ascii")
    (source / "token").chmod(0o600)
    return source


@pytest.fixture
def target(tmp_path: Path) -> Path:
    destination = tmp_path / "runtime"
    destination.mkdir()
    return destination


def _owner() -> tuple[int, int]:
    return os.getuid(), os.getgid()


def test_sync_publishes_worker_owned_private_files(credentials: Path, target: Path) -> None:
    uid, gid = _owner()
    sync_once(credentials, target, uid, gid)

    assert (target / "ca.pem").read_bytes() == _CA
    assert (target / "token").read_text(encoding="ascii") == "synthetic-token"
    directory = target.stat()
    assert (directory.st_uid, directory.st_gid, stat.S_IMODE(directory.st_mode)) == (
        uid,
        gid,
        0o700,
    )
    for name in ("ca.pem", "token"):
        details = (target / name).stat()
        assert (details.st_uid, details.st_gid, stat.S_IMODE(details.st_mode)) == (
            uid,
            gid,
            0o600,
        )
    check_target(target, uid, gid)


def test_token_replacement_is_atomic(credentials: Path, target: Path) -> None:
    uid, gid = _owner()
    sync_once(credentials, target, uid, gid)
    with (target / "token").open(encoding="ascii") as previous:
        (credentials / "token").write_text("synthetic-renewed-token", encoding="ascii")
        sync_once(credentials, target, uid, gid)
        assert previous.read() == "synthetic-token"
    assert (target / "token").read_text(encoding="ascii") == "synthetic-renewed-token"


@pytest.mark.parametrize(
    ("name", "content", "mode"),
    [
        ("token", "two tokens", 0o600),
        ("token", "synthetic-token\n", 0o600),
        ("token", "synthetic-token", 0o644),
        ("ca.pem", "not a certificate", 0o600),
    ],
)
def test_invalid_source_is_rejected_and_removes_published_credentials(
    credentials: Path,
    target: Path,
    name: str,
    content: str,
    mode: int,
) -> None:
    uid, gid = _owner()
    sync_once(credentials, target, uid, gid)
    (credentials / name).write_text(content, encoding="ascii")
    (credentials / name).chmod(mode)

    assert not sync_or_remove(credentials, target, uid, gid)

    assert not (target / "ca.pem").exists()
    assert not (target / "token").exists()


def test_source_symlink_is_rejected(credentials: Path, target: Path, tmp_path: Path) -> None:
    (credentials / "token").unlink()
    secret = tmp_path / "outside-token"
    secret.write_text("synthetic-token", encoding="ascii")
    secret.chmod(0o600)
    (credentials / "token").symlink_to(secret)

    with pytest.raises(CredentialSyncError):
        sync_once(credentials, target, *_owner())


def test_target_check_rejects_broad_file_permissions(credentials: Path, target: Path) -> None:
    uid, gid = _owner()
    sync_once(credentials, target, uid, gid)
    (target / "token").chmod(0o644)

    with pytest.raises(CredentialSyncError):
        check_target(target, uid, gid)
