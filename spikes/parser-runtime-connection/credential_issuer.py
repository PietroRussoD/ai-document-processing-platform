"""Provision and renew a bound controller token outside the application worker."""

import argparse
import json
import os
import signal
import stat
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from connection_probe import ConnectionSettings, ProbeError

CONTEXT = "kind-ai-doc-parser-credential-probe"
NAMESPACE = "pdf-parser-probe"
ACCOUNT = "parser-controller"
ANCHOR = "parser-controller-session"


@dataclass(frozen=True)
class IssuedToken:
    token: str = field(repr=False)
    expires_at: datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def kubectl(kubeconfig: Path, *arguments: str, body: str | None = None) -> str:
    try:
        result = subprocess.run(
            ["kubectl", "--kubeconfig", str(kubeconfig), "--context", CONTEXT, *arguments],
            input=body,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        raise ProbeError("Credential provisioning command failed") from None
    if len(result.stdout) > 65_536:
        raise ProbeError("Credential provisioning response exceeded its limit")
    return result.stdout


class TokenIssuer:
    def __init__(self, kubeconfig: Path, bound_uid: str, ttl: int = 3600) -> None:
        if not kubeconfig.is_absolute() or not kubeconfig.is_file():
            raise ProbeError("Use an explicit absolute bootstrap kubeconfig file")
        if not bound_uid or not 600 <= ttl <= 3600:
            raise ProbeError(
                "Use a pinned binding UID and a token lifetime from 600 to 3600 seconds"
            )
        self.kubeconfig = kubeconfig
        self.bound_uid = bound_uid
        self.ttl = ttl
        try:
            configuration = json.loads(
                kubectl(kubeconfig, "config", "view", "--minify", "-o", "json")
            )
            cluster = configuration["clusters"][0]["cluster"]
            if cluster.get("insecure-skip-tls-verify") or cluster.get("proxy-url"):
                raise ProbeError("Bootstrap configuration must verify TLS without a proxy")
            ConnectionSettings(
                cluster["server"], NAMESPACE, Path("unused-ca"), Path("unused-token")
            )
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProbeError("Bootstrap kubeconfig has no valid local endpoint") from None

    def issue(self) -> IssuedToken:
        body = {
            "apiVersion": "authentication.k8s.io/v1",
            "kind": "TokenRequest",
            "spec": {
                "expirationSeconds": self.ttl,
                "boundObjectRef": {
                    "kind": "Secret",
                    "apiVersion": "v1",
                    "name": ANCHOR,
                    "uid": self.bound_uid,
                },
            },
        }
        response = kubectl(
            self.kubeconfig,
            "create",
            "--raw",
            f"/api/v1/namespaces/{NAMESPACE}/serviceaccounts/{ACCOUNT}/token",
            "-f",
            "-",
            body=json.dumps(body),
        )
        try:
            status = json.loads(response)["status"]
            token = status["token"]
            expires_at = datetime.fromisoformat(status["expirationTimestamp"])
            lifetime = (expires_at - utc_now()).total_seconds()
            if (
                not isinstance(token, str)
                or not 1 <= len(token) <= 16_384
                or any(ord(character) < 33 or ord(character) > 126 for character in token)
                or not 0 < lifetime <= self.ttl + 60
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise ProbeError("Issuer returned an invalid token or expiration") from None
        return IssuedToken(token, expires_at)


def check_directory(directory: Path) -> None:
    info = directory.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise ProbeError("Credential directory must be owned by the provisioner with mode 0700")


def publish_token(directory: Path, token: str) -> None:
    check_directory(directory)
    descriptor, temporary = tempfile.mkstemp(prefix=".token-", dir=directory)
    try:
        with os.fdopen(descriptor, "w", encoding="ascii") as target:
            target.write(token)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, directory / "token")
    finally:
        Path(temporary).unlink(missing_ok=True)


def remove_token(directory: Path) -> None:
    check_directory(directory)
    (directory / "token").unlink(missing_ok=True)


def emit(event: str) -> None:
    print(json.dumps({"event": event}), flush=True)


class TokenRenewer:
    def __init__(
        self,
        issue: Callable[[], IssuedToken],
        directory: Path,
        renew_before: int = 300,
    ) -> None:
        self.issue = issue
        self.directory = directory
        self.renew_before = renew_before
        self.expires_at: datetime | None = None

    def tick(self, now: datetime) -> float:
        if self.expires_at is not None:
            remaining = (self.expires_at - now).total_seconds()
            if remaining <= 0:
                remove_token(self.directory)
                self.expires_at = None
                emit("expired")
            elif remaining > self.renew_before:
                return min(30, remaining - self.renew_before)
        try:
            issued = self.issue()
            if issued.expires_at <= now:
                raise ProbeError("Issuer returned an expired token")
            publish_token(self.directory, issued.token)
        except ProbeError:
            # An unsuccessful renewal must not extend the previous token's local lifetime.
            if self.expires_at is None:
                remove_token(self.directory)
                emit("unavailable")
                return 10
            emit("renewal_failed")
            return min(10, max(0, (self.expires_at - utc_now()).total_seconds()))
        self.expires_at = issued.expires_at
        emit("renewed")
        return min(
            30, max(0.1, (issued.expires_at - utc_now()).total_seconds() - self.renew_before)
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kubeconfig", required=True, type=Path)
    parser.add_argument("--credential-dir", required=True, type=Path)
    parser.add_argument("--bound-uid", required=True)
    parser.add_argument("--ttl", type=int, default=3600)
    parser.add_argument("--renew-before", type=int, default=300)
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    try:
        if not 0 < args.renew_before < args.ttl:
            raise ProbeError(
                "Renewal margin must be positive and shorter than the requested lifetime"
            )
        check_directory(args.credential_dir)
        issuer = TokenIssuer(args.kubeconfig, args.bound_uid, args.ttl)
        renewer = TokenRenewer(issuer.issue, args.credential_dir, args.renew_before)

        def stop(signum: int, frame: object) -> None:
            raise KeyboardInterrupt

        if args.watch:
            signal.signal(signal.SIGTERM, stop)
        try:
            while True:
                delay = renewer.tick(utc_now())
                if not args.watch:
                    return 0 if renewer.expires_at else 1
                time.sleep(delay)
        finally:
            if args.watch:
                remove_token(args.credential_dir)
    except KeyboardInterrupt:
        emit("stopped")
        return 130
    except Exception:
        emit("failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
