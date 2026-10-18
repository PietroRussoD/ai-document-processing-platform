"""Connection boundary checks independent of the application's test environment."""

from dataclasses import replace
from pathlib import Path

import certifi
import connection_probe
import pytest
from connection_probe import ConnectionSettings, ProbeError, build_configuration, verify_connection
from kubernetes import client
from kubernetes.client.exceptions import ApiException


@pytest.fixture
def settings(tmp_path: Path) -> ConnectionSettings:
    token_file = tmp_path / "token"
    token_file.write_text("synthetic-controller-token\n")
    return ConnectionSettings(
        "https://127.0.0.1:6443", "pdf-parser-probe", Path(certifi.where()), token_file
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://127.0.0.1:6443",
        "https://remote.example:6443",
        "https://127.0.0.1",
        "https://127.0.0.1:0",
        "https://127.0.0.1:65536",
        "https://admin:secret@127.0.0.1:6443",
        "https://127.0.0.1:6443/api",
        "https://127.0.0.1:6443/?token=secret",
        "https://127.0.0.1:6443/#fragment",
        "https://127.0.0.1:6443\n",
    ],
)
def test_rejects_ambiguous_or_remote_endpoints(settings: ConnectionSettings, endpoint: str) -> None:
    with pytest.raises(ProbeError, match="local HTTPS"):
        replace(settings, endpoint=endpoint)


@pytest.mark.parametrize("namespace", ["default", "kube-system", "", "Invalid", "a/b", "x" * 64])
def test_requires_a_dedicated_namespace(settings: ConnectionSettings, namespace: str) -> None:
    with pytest.raises(ProbeError, match="dedicated"):
        replace(settings, namespace=namespace)


def test_uses_only_explicit_ca_and_bearer_credentials(
    settings: ConnectionSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    ambient = client.Configuration()
    ambient.host = "https://remote.example:6443"
    ambient.verify_ssl = False
    ambient.cert_file = "administrator.crt"
    ambient.key_file = "administrator.key"
    ambient.api_key = {"authorization": "synthetic-administrator-token"}
    monkeypatch.setattr(client.Configuration, "_default", ambient)
    monkeypatch.setenv("KUBECONFIG", "/unreadable/administrator-kubeconfig")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:8080")

    configuration = build_configuration(settings)

    assert configuration.host == settings.endpoint
    assert configuration.ssl_ca_cert == str(settings.ca_file)
    assert configuration.verify_ssl is True
    assert configuration.assert_hostname is not False
    assert configuration.cert_file is None
    assert configuration.key_file is None
    assert configuration.username is None
    assert configuration.password is None
    assert configuration.proxy is None
    assert configuration.debug is False
    assert configuration.retries == 0
    assert configuration.get_api_key_with_prefix("authorization") == (
        "Bearer synthetic-controller-token"
    )


def test_reloads_rotated_token_and_fails_when_it_disappears(settings: ConnectionSettings) -> None:
    configuration = build_configuration(settings)
    settings.token_file.write_text("synthetic-rotated-token")
    assert (
        configuration.get_api_key_with_prefix("authorization") == "Bearer synthetic-rotated-token"
    )
    settings.token_file.unlink()
    with pytest.raises(ProbeError, match="unreadable"):
        configuration.get_api_key_with_prefix("authorization")


@pytest.mark.parametrize("token", ["", "\n", "two tokens", "one\ntwo", "a\x00b", "x" * 16_385])
def test_rejects_invalid_token_files(settings: ConnectionSettings, token: str) -> None:
    settings.token_file.write_text(token)
    with pytest.raises(ProbeError):
        build_configuration(settings)


def test_rejects_an_invalid_ca(settings: ConnectionSettings, tmp_path: Path) -> None:
    ca_file = tmp_path / "invalid-ca.pem"
    ca_file.write_text("not a certificate")
    with pytest.raises(ProbeError, match="CA file"):
        build_configuration(replace(settings, ca_file=ca_file))


def mock_permissions(monkeypatch: pytest.MonkeyPatch, override: str | None = None) -> None:
    monkeypatch.setattr(client.CoreV1Api, "list_namespaced_pod", lambda *args, **kwargs: None)

    def review(self, body, **kwargs):
        attributes = body.spec.resource_attributes
        allowed = attributes.namespace == "pdf-parser-probe" and (
            attributes.resource == "jobs"
            or attributes.resource == "pods"
            and (attributes.subresource == "exec" or attributes.verb != "create")
        )
        if override == "secrets" and attributes.resource == "secrets":
            allowed = True
        if override == "missing-exec" and attributes.subresource == "exec":
            allowed = False
        if override == "other-namespace" and attributes.namespace == "default":
            allowed = True
        if override == "self-renewal" and attributes.resource == "serviceaccounts":
            allowed = True
        return client.V1SelfSubjectAccessReview(
            spec=body.spec,
            status=client.V1SubjectAccessReviewStatus(
                allowed=allowed,
                evaluation_error="synthetic-evaluation-error"
                if override == "evaluation-error"
                else None,
            ),
        )

    monkeypatch.setattr(client.AuthorizationV1Api, "create_self_subject_access_review", review)


def test_accepts_the_expected_scoped_permissions(
    settings: ConnectionSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_permissions(monkeypatch)
    assert verify_connection(settings) == {
        "tls": "verified",
        "required_rbac": "allowed",
        "checked_denials": "denied",
    }


@pytest.mark.parametrize("override", ["secrets", "missing-exec", "other-namespace", "self-renewal"])
def test_rejects_missing_or_excess_permissions(
    settings: ConnectionSettings, monkeypatch: pytest.MonkeyPatch, override: str
) -> None:
    mock_permissions(monkeypatch, override)
    with pytest.raises(ProbeError, match="RBAC"):
        verify_connection(settings)


def test_rejects_an_inconclusive_permission_evaluation(
    settings: ConnectionSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_permissions(monkeypatch, "evaluation-error")
    with pytest.raises(ProbeError, match="could not evaluate"):
        verify_connection(settings)


def test_does_not_expose_api_error_bodies(
    settings: ConnectionSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refused(*args, **kwargs):
        raise ApiException(status=401, reason="synthetic-secret", http_resp=None)

    monkeypatch.setattr(client.CoreV1Api, "list_namespaced_pod", refused)
    with pytest.raises(ProbeError, match="HTTP 401") as error:
        verify_connection(settings)
    assert "synthetic-secret" not in str(error.value)


def test_cli_does_not_expose_unexpected_exception_details(
    settings: ConnectionSettings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def malformed_response(*args):
        raise ValueError("synthetic-secret-in-response")

    monkeypatch.setattr(connection_probe, "verify_connection", malformed_response)
    monkeypatch.setattr(
        "sys.argv",
        [
            "connection_probe.py",
            "--endpoint",
            settings.endpoint,
            "--namespace",
            settings.namespace,
            "--ca-file",
            str(settings.ca_file),
            "--token-file",
            str(settings.token_file),
        ],
    )
    assert connection_probe.main() == 1
    output = capsys.readouterr()
    assert "Unexpected Kubernetes client response" in output.err
    assert "synthetic-secret-in-response" not in output.err
    assert output.out == ""
