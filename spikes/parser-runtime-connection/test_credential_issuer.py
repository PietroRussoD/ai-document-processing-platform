"""Synthetic issuance and clock-controlled renewal failure checks."""

import json
import os
import stat
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import credential_issuer
import pytest
from connection_probe import ProbeError
from credential_issuer import IssuedToken, TokenIssuer, TokenRenewer, publish_token

NOW = datetime(2026, 10, 18, 12, tzinfo=UTC)


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    root = tmp_path / "credentials"
    root.mkdir(mode=0o700)
    return root


@pytest.fixture
def issuer(tmp_path: Path, monkeypatch):
    kubeconfig = tmp_path / "admin.kubeconfig"
    kubeconfig.touch(mode=0o600)
    command = Mock(
        return_value=json.dumps({"clusters": [{"cluster": {"server": "https://127.0.0.1:6443"}}]})
    )
    monkeypatch.setattr(credential_issuer, "kubectl", command)
    monkeypatch.setattr(credential_issuer, "utc_now", lambda: NOW)
    instance = TokenIssuer(kubeconfig, "synthetic-binding-uid")
    command.reset_mock()
    return instance, command


def test_request_pins_anchor_and_lifetime(issuer) -> None:
    instance, command = issuer
    command.return_value = json.dumps(
        {
            "status": {
                "token": "synthetic-token",
                "expirationTimestamp": (NOW + timedelta(hours=1)).isoformat(),
            }
        }
    )
    issued = instance.issue()
    assert issued.token == "synthetic-token"
    assert "synthetic-token" not in repr(issued)
    body = json.loads(command.call_args.kwargs["body"])
    assert body["spec"]["expirationSeconds"] == 3600
    assert body["spec"]["boundObjectRef"] == {
        "kind": "Secret",
        "apiVersion": "v1",
        "name": "parser-controller-session",
        "uid": "synthetic-binding-uid",
    }
    assert (
        "/api/v1/namespaces/pdf-parser-probe/serviceaccounts/parser-controller/token"
        in command.call_args.args
    )


@pytest.mark.parametrize(
    "token,seconds",
    [
        ("", 3600),
        ("two tokens", 3600),
        ("x" * 16_385, 3600),
        ("synthetic-token", -1),
        ("synthetic-token", 7200),
    ],
)
def test_refuses_bad_issuance(issuer, token, seconds) -> None:
    instance, command = issuer
    command.return_value = json.dumps(
        {
            "status": {
                "token": token,
                "expirationTimestamp": (NOW + timedelta(seconds=seconds)).isoformat(),
            }
        }
    )
    with pytest.raises(ProbeError, match="invalid token or expiration"):
        instance.issue()


@pytest.mark.parametrize(
    "cluster",
    [
        {"server": "https://remote.example:6443"},
        {"server": "https://127.0.0.1:6443", "insecure-skip-tls-verify": True},
        {"server": "https://127.0.0.1:6443", "proxy-url": "http://proxy.example"},
    ],
)
def test_rejects_remote_or_insecure_bootstrap(issuer, monkeypatch, cluster) -> None:
    instance, command = issuer
    command.return_value = json.dumps({"clusters": [{"cluster": cluster}]})
    with pytest.raises(ProbeError):
        TokenIssuer(instance.kubeconfig, "synthetic-binding-uid")


def test_kubectl_uses_explicit_credentials_without_secret_arguments(monkeypatch) -> None:
    command = Mock(return_value=subprocess.CompletedProcess([], 0, stdout="{}", stderr=""))
    monkeypatch.setattr(subprocess, "run", command)
    credential_issuer.kubectl(Path("/synthetic/admin.kubeconfig"), "create", body="synthetic-body")
    arguments = command.call_args.args[0]
    assert arguments[:5] == [
        "kubectl",
        "--kubeconfig",
        "/synthetic/admin.kubeconfig",
        "--context",
        "kind-ai-doc-parser-credential-probe",
    ]
    assert "synthetic-body" not in arguments
    assert command.call_args.kwargs["input"] == "synthetic-body"
    assert command.call_args.kwargs["timeout"] == 10
    command.side_effect = subprocess.CalledProcessError(1, arguments, stderr="synthetic-secret")
    with pytest.raises(ProbeError) as error:
        credential_issuer.kubectl(Path("/synthetic/admin.kubeconfig"), "create")
    assert "synthetic-secret" not in str(error.value)


def test_issuer_accepts_only_explicit_bootstrap_context(issuer) -> None:
    instance, command = issuer
    instance = TokenIssuer(
        instance.kubeconfig,
        "synthetic-binding-uid",
        context="kind-ai-doc-parser-runtime-cafefeed0",
    )
    assert command.call_args.kwargs["context"] == "kind-ai-doc-parser-runtime-cafefeed0"
    command.reset_mock()
    command.return_value = json.dumps(
        {
            "status": {
                "token": "synthetic-token",
                "expirationTimestamp": (NOW + timedelta(hours=1)).isoformat(),
            }
        }
    )
    instance.issue()
    assert command.call_args.kwargs["context"] == "kind-ai-doc-parser-runtime-cafefeed0"


def test_atomic_private_publication_preserves_previous_on_failure(directory, monkeypatch) -> None:
    publish_token(directory, "synthetic-old")
    with (directory / "token").open() as old:
        publish_token(directory, "synthetic-new")
        assert old.read() == "synthetic-old"
    assert (directory / "token").read_text() == "synthetic-new"
    assert stat.S_IMODE((directory / "token").stat().st_mode) == 0o600
    assert (directory / "token").stat().st_uid == os.geteuid()
    monkeypatch.setattr(credential_issuer.os, "replace", Mock(side_effect=OSError))
    with pytest.raises(OSError):
        publish_token(directory, "synthetic-unpublished")
    assert (directory / "token").read_text() == "synthetic-new"
    assert sorted(entry.name for entry in directory.iterdir()) == ["token"]


def test_rejects_public_or_symlinked_directory(directory, tmp_path) -> None:
    directory.chmod(0o755)
    with pytest.raises(ProbeError, match="0700"):
        publish_token(directory, "synthetic-token")
    directory.chmod(0o700)
    link = tmp_path / "linked"
    link.symlink_to(directory)
    with pytest.raises(ProbeError, match="0700"):
        publish_token(link, "synthetic-token")


def test_failed_renewal_never_extends_expiry(directory, monkeypatch, capsys) -> None:
    monkeypatch.setattr(credential_issuer, "utc_now", lambda: NOW)
    issue = Mock(
        side_effect=[
            IssuedToken("synthetic-token", NOW + timedelta(seconds=600)),
            ProbeError(),
            ProbeError(),
        ]
    )
    renewer = TokenRenewer(issue, directory, renew_before=300)
    assert renewer.tick(NOW) == 30
    assert renewer.tick(NOW + timedelta(seconds=299)) == 1
    assert issue.call_count == 1
    renewer.tick(NOW + timedelta(seconds=300))
    assert renewer.expires_at == NOW + timedelta(seconds=600)
    assert (directory / "token").read_text() == "synthetic-token"
    renewer.tick(NOW + timedelta(seconds=600))
    assert not (directory / "token").exists()
    assert renewer.expires_at is None
    output = capsys.readouterr().out
    assert "synthetic-token" not in output
    assert all(event in output for event in ["renewed", "renewal_failed", "expired", "unavailable"])


def test_successful_renewal_replaces_token_and_expiry(directory, monkeypatch) -> None:
    monkeypatch.setattr(credential_issuer, "utc_now", lambda: NOW)
    issue = Mock(
        side_effect=[
            IssuedToken("synthetic-old", NOW + timedelta(seconds=600)),
            IssuedToken("synthetic-new", NOW + timedelta(seconds=900)),
        ]
    )
    renewer = TokenRenewer(issue, directory)
    renewer.tick(NOW)
    renewer.tick(NOW + timedelta(seconds=300))
    assert (directory / "token").read_text() == "synthetic-new"
    assert renewer.expires_at == NOW + timedelta(seconds=900)


def test_failed_start_removes_unknown_stale_token(directory) -> None:
    publish_token(directory, "synthetic-stale")
    renewer = TokenRenewer(Mock(side_effect=ProbeError()), directory)
    renewer.tick(NOW)
    assert not (directory / "token").exists()
