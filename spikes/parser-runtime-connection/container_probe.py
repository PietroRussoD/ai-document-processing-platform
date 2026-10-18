"""Exercise credential mounts and token replacement in the worker's container image."""

import argparse
import errno
import json
import os
import stat
import sys
from pathlib import Path

from connection_probe import (
    REQUEST_TIMEOUT,
    ConnectionSettings,
    ProbeError,
    build_configuration,
    verify_connection,
)
from kubernetes import client
from kubernetes.client.exceptions import ApiException
from urllib3.exceptions import HTTPError


def verify_mount(credentials_dir: Path) -> None:
    if (os.getuid(), os.getgid()) != (10001, 10001):
        raise ProbeError("Container must run as UID and GID 10001")
    for candidate, mode in (
        (credentials_dir, 0o700),
        (credentials_dir / "ca.pem", 0o600),
        (credentials_dir / "token", 0o600),
    ):
        details = candidate.stat()
        if (details.st_uid, details.st_gid, stat.S_IMODE(details.st_mode)) != (10001, 10001, mode):
            raise ProbeError(
                "Credential ownership or permissions do not match the expected boundary"
            )

    candidate = credentials_dir / ".readonly-check"
    try:
        with candidate.open("x"):
            pass
    except OSError as error:
        if error.errno != errno.EROFS:
            raise ProbeError("Expected a read-only credential filesystem") from None
    else:
        candidate.unlink()
        raise ProbeError("Credential mount unexpectedly allows writes")


def emit(result: dict[str, object]) -> None:
    print(json.dumps(result), flush=True)


def run(settings: ConnectionSettings) -> None:
    verify_mount(settings.token_file.parent)
    verify_connection(settings)
    configuration = build_configuration(settings)
    # Reuse one client so replacement checks exercise the SDK's token refresh hook.
    with client.ApiClient(configuration=configuration) as api:
        core = client.CoreV1Api(api)
        core.list_namespaced_pod(settings.namespace, limit=1, _request_timeout=REQUEST_TIMEOUT)
        emit(
            {"event": "ready", "uid": os.getuid(), "credentials_readonly": True, "tls": "verified"}
        )
        for line in sys.stdin:
            command = line.strip()
            if command == "stop":
                return
            if command != "check":
                raise ProbeError("Unknown container probe command")
            try:
                core.list_namespaced_pod(
                    settings.namespace, limit=1, _request_timeout=REQUEST_TIMEOUT
                )
            except ProbeError as error:
                emit({"event": "check", "result": "refused", "reason": str(error)})
            except ApiException as error:
                status = getattr(error, "status", None)
                status_code = status if isinstance(status, int) else None
                emit({"event": "check", "result": "refused", "http_status": status_code})
            except (HTTPError, OSError):
                emit({"event": "check", "result": "refused", "reason": "TLS or network failure"})
            else:
                emit({"event": "check", "result": "accepted"})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--namespace", default="pdf-parser-probe")
    parser.add_argument("--credentials-dir", type=Path, default=Path("/run/parser-controller"))
    args = parser.parse_args()
    try:
        run(
            ConnectionSettings(
                args.endpoint,
                args.namespace,
                args.credentials_dir / "ca.pem",
                args.credentials_dir / "token",
            )
        )
    except ProbeError as error:
        emit({"event": "failed", "reason": str(error)})
        return 1
    except Exception:
        emit({"event": "failed", "reason": "Container credential or connection check failed"})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
