"""Copy private host credentials into the worker's read-only Docker volume."""

import argparse
import os
import signal
import stat
import tempfile
import time
from pathlib import Path

_DEFAULT_UID = 10001
_DEFAULT_GID = 10001
_MAX_CA_BYTES = 65_536
_MAX_TOKEN_BYTES = 16_384
_POLL_SECONDS = 1


class CredentialSyncError(RuntimeError):
    """Credential inputs or the runtime volume violate the sync contract."""


def _check_directory(path: Path, mode: int | None = None) -> os.stat_result:
    try:
        details = path.lstat()
    except OSError:
        raise CredentialSyncError("Credential directory is unavailable") from None
    if not stat.S_ISDIR(details.st_mode) or (
        mode is not None and stat.S_IMODE(details.st_mode) != mode
    ):
        raise CredentialSyncError("Credential directory has an invalid type or mode")
    return details


def _read_source_file(directory: Path, name: str, maximum_bytes: int) -> bytes:
    path = directory / name
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        details = os.fstat(descriptor)
        if (
            not stat.S_ISREG(details.st_mode)
            or stat.S_IMODE(details.st_mode) != 0o600
            or details.st_size < 1
            or details.st_size > maximum_bytes
        ):
            raise CredentialSyncError("Credential file has an invalid type, mode or size")
        chunks: list[bytes] = []
        remaining = maximum_bytes + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 8192))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    except CredentialSyncError:
        raise
    except OSError:
        raise CredentialSyncError("Credential file is unavailable") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
    content = b"".join(chunks)
    if len(content) > maximum_bytes:
        raise CredentialSyncError("Credential file exceeds its size limit")
    return content


def _validate_credentials(source: Path) -> tuple[bytes, bytes]:
    _check_directory(source, 0o700)
    ca = _read_source_file(source, "ca.pem", _MAX_CA_BYTES)
    token = _read_source_file(source, "token", _MAX_TOKEN_BYTES)
    if b"-----BEGIN CERTIFICATE-----" not in ca or b"-----END CERTIFICATE-----" not in ca:
        raise CredentialSyncError("Credential CA is not a PEM certificate")
    try:
        token_text = token.decode("ascii")
    except UnicodeDecodeError:
        raise CredentialSyncError("Credential token is not valid ASCII") from None
    if any(ord(character) < 33 or ord(character) > 126 for character in token_text):
        raise CredentialSyncError("Credential token contains invalid characters")
    return ca, token


def _prepare_target(target: Path, uid: int, gid: int) -> None:
    details = _check_directory(target)
    owner = (details.st_uid, details.st_gid)
    mode = stat.S_IMODE(details.st_mode)
    if owner == (uid, gid) and mode == 0o700:
        return
    if owner not in {(0, 0), (uid, gid)}:
        raise CredentialSyncError("Credential volume has unexpected ownership")
    try:
        if owner == (0, 0):
            os.chmod(target, 0o700)
            os.chown(target, uid, gid)
        elif (os.geteuid(), os.getegid()) == (uid, gid):
            os.chmod(target, 0o700)
        else:
            # The root delivery helper has CHOWN but deliberately lacks FOWNER.
            os.chown(target, 0, 0)
            os.chmod(target, 0o700)
            os.chown(target, uid, gid)
    except OSError:
        raise CredentialSyncError("Credential volume cannot be prepared for the worker") from None


def _matches(path: Path, content: bytes, uid: int, gid: int) -> bool:
    try:
        details = path.lstat()
        if (
            not stat.S_ISREG(details.st_mode)
            or (details.st_uid, details.st_gid, stat.S_IMODE(details.st_mode)) != (uid, gid, 0o600)
            or details.st_size != len(content)
        ):
            return False
        return path.read_bytes() == content
    except OSError:
        return False


def _publish(target: Path, name: str, content: bytes, uid: int, gid: int) -> None:
    destination = target / name
    if _matches(destination, content, uid, gid):
        return
    descriptor, temporary = tempfile.mkstemp(prefix=f".{name}-", dir=target)
    try:
        os.fchmod(descriptor, 0o600)
        os.fchown(descriptor, uid, gid)
        with os.fdopen(descriptor, "wb") as output:
            descriptor = -1
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
        directory_fd = os.open(target, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError:
        raise CredentialSyncError("Credential volume update failed") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        Path(temporary).unlink(missing_ok=True)


def sync_once(source: Path, target: Path, uid: int = _DEFAULT_UID, gid: int = _DEFAULT_GID) -> None:
    ca, token = _validate_credentials(source)
    _prepare_target(target, uid, gid)
    _publish(target, "ca.pem", ca, uid, gid)
    _publish(target, "token", token, uid, gid)


def _remove_target_credentials(target: Path) -> None:
    try:
        _check_directory(target)
        for name in ("token", "ca.pem"):
            (target / name).unlink(missing_ok=True)
    except (CredentialSyncError, OSError):
        return


def sync_or_remove(
    source: Path, target: Path, uid: int = _DEFAULT_UID, gid: int = _DEFAULT_GID
) -> bool:
    try:
        sync_once(source, target, uid, gid)
    except CredentialSyncError:
        _remove_target_credentials(target)
        return False
    return True


def check_target(target: Path, uid: int = _DEFAULT_UID, gid: int = _DEFAULT_GID) -> None:
    details = _check_directory(target, 0o700)
    if (details.st_uid, details.st_gid) != (uid, gid):
        raise CredentialSyncError("Credential volume has invalid worker ownership")
    ca = _read_target_file(target, "ca.pem", _MAX_CA_BYTES, uid, gid)
    token = _read_target_file(target, "token", _MAX_TOKEN_BYTES, uid, gid)
    if b"-----BEGIN CERTIFICATE-----" not in ca or b"-----END CERTIFICATE-----" not in ca:
        raise CredentialSyncError("Credential CA is not a PEM certificate")
    try:
        token_text = token.decode("ascii")
    except UnicodeDecodeError:
        raise CredentialSyncError("Credential token is not valid ASCII") from None
    if any(ord(character) < 33 or ord(character) > 126 for character in token_text):
        raise CredentialSyncError("Credential token contains invalid characters")


def _read_target_file(directory: Path, name: str, maximum_bytes: int, uid: int, gid: int) -> bytes:
    path = directory / name
    try:
        details = path.lstat()
        if (
            not stat.S_ISREG(details.st_mode)
            or (details.st_uid, details.st_gid, stat.S_IMODE(details.st_mode)) != (uid, gid, 0o600)
            or not 1 <= details.st_size <= maximum_bytes
        ):
            raise CredentialSyncError("Credential volume file has invalid metadata")
        return path.read_bytes()
    except CredentialSyncError:
        raise
    except OSError:
        raise CredentialSyncError("Credential volume file is unavailable") from None


def _watch(source: Path, target: Path, uid: int, gid: int, poll_seconds: int) -> int:
    stopping = False

    def stop(signum: int, frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    last_state: str | None = None
    while not stopping:
        state = "synced" if sync_or_remove(source, target, uid, gid) else "unavailable"
        if state != last_state:
            print(state, flush=True)
            last_state = state
        time.sleep(poll_seconds)
    print("stopped", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=Path("/run/parser-source"))
    parser.add_argument("--target-dir", type=Path, default=Path("/run/parser-runtime"))
    parser.add_argument("--uid", type=int, default=_DEFAULT_UID)
    parser.add_argument("--gid", type=int, default=_DEFAULT_GID)
    parser.add_argument("--poll-seconds", type=int, default=_POLL_SECONDS)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--watch", action="store_true")
    mode.add_argument("--check-target", action="store_true")
    args = parser.parse_args()
    if min(args.uid, args.gid) < 1 or not 1 <= args.poll_seconds <= 30:
        parser.error("UID/GID must be positive and poll interval must be 1–30 seconds")
    try:
        if args.check_target:
            check_target(args.target_dir, args.uid, args.gid)
            return 0
        return _watch(args.source_dir, args.target_dir, args.uid, args.gid, args.poll_seconds)
    except CredentialSyncError as error:
        print(str(error), flush=True)
        return 1
    except Exception:
        print("Credential sync failed", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
