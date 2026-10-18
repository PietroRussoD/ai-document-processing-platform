"""Explicit Kubernetes parser-runtime connection tests."""

import ssl
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
import urllib3.exceptions
from kubernetes import client
from kubernetes.client.exceptions import ApiException

import document_platform.adapters.outbound.kubernetes.parser_runtime_connection as connection_module
from document_platform.adapters.outbound.kubernetes import (
    KubernetesParserRuntimeConnection,
    KubernetesParserRuntimeSettings,
)
from document_platform.application.ports import ParserRuntimeRejected, ParserRuntimeUnavailable


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> KubernetesParserRuntimeSettings:
    token_file = tmp_path / "controller-token"
    token_file.write_text("synthetic-controller-token\n")
    ca_file = tmp_path / "ca.pem"
    ca_file.write_text("synthetic CA fixture")

    def stub_context(**kwargs: object) -> object:
        return object()

    monkeypatch.setattr(cast(Any, connection_module.ssl), "create_default_context", stub_context)
    return KubernetesParserRuntimeSettings(
        "https://127.0.0.1:6443", "pdf-parser", ca_file, token_file
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://127.0.0.1:6443",
        "https://remote.example:6443",
        "https://127.0.0.1",
        "https://127.0.0.1:0",
        "https://admin:secret@127.0.0.1:6443",
        "https://127.0.0.1:6443/api",
        "https://127.0.0.1:6443/?token=secret",
    ],
)
def test_rejects_ambiguous_or_remote_endpoints(
    settings: KubernetesParserRuntimeSettings, endpoint: str
) -> None:
    with pytest.raises(ParserRuntimeRejected, match="explicit local HTTPS"):
        replace(settings, endpoint=endpoint)


@pytest.mark.parametrize("namespace", ["default", "kube-system", "", "Invalid", "a/b"])
def test_requires_a_dedicated_namespace(
    settings: KubernetesParserRuntimeSettings, namespace: str
) -> None:
    with pytest.raises(ParserRuntimeRejected, match="dedicated valid"):
        replace(settings, namespace=namespace)


def test_uses_only_explicit_ca_and_bearer_credentials(
    settings: KubernetesParserRuntimeSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ambient = client.Configuration()
    ambient.host = "https://remote.example:6443"
    ambient.verify_ssl = False
    ambient.api_key = {"authorization": "synthetic-admin-token"}
    monkeypatch.setattr(client.Configuration, "_default", ambient)
    monkeypatch.setenv("KUBECONFIG", "/unreadable/admin-kubeconfig")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:8080")

    api = KubernetesParserRuntimeConnection(settings).new_api_client()
    try:
        configuration = cast(client.Configuration, cast(Any, api).configuration)
        get_api_key = cast(Callable[[str], str | None], configuration.get_api_key_with_prefix)
        assert configuration.host == settings.endpoint
        assert configuration.ssl_ca_cert == str(settings.ca_file)
        assert configuration.verify_ssl is True
        assert configuration.cert_file is None
        assert configuration.key_file is None
        assert configuration.proxy is None
        assert configuration.debug is False
        assert get_api_key("authorization") == ("Bearer synthetic-controller-token")
    finally:
        api.close()


def test_reads_rotated_token_for_the_next_api_request(
    settings: KubernetesParserRuntimeSettings,
) -> None:
    api = KubernetesParserRuntimeConnection(settings).new_api_client()
    try:
        settings.token_file.write_text("synthetic-rotated-token")
        configuration = cast(client.Configuration, cast(Any, api).configuration)
        get_api_key = cast(Callable[[str], str | None], configuration.get_api_key_with_prefix)
        assert get_api_key("authorization") == ("Bearer synthetic-rotated-token")
    finally:
        api.close()


def test_rejects_unreadable_token(settings: KubernetesParserRuntimeSettings) -> None:
    settings.token_file.unlink()

    with pytest.raises(ParserRuntimeRejected, match="token file is unreadable"):
        KubernetesParserRuntimeConnection(settings).new_api_client()


def test_rejects_invalid_ca(
    settings: KubernetesParserRuntimeSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def invalid_ca(**kwargs: object) -> object:
        raise ssl.SSLError("private CA details")

    monkeypatch.setattr(cast(Any, connection_module.ssl), "create_default_context", invalid_ca)
    with pytest.raises(ParserRuntimeRejected, match="CA file is unreadable or invalid"):
        KubernetesParserRuntimeConnection(settings).new_api_client()


def test_maps_successful_api_access_to_ready(
    settings: KubernetesParserRuntimeSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def list_pods(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(client.CoreV1Api, "list_namespaced_pod", list_pods)
    KubernetesParserRuntimeConnection(settings).verify_connection()

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[1] == "pdf-parser"
    assert kwargs == {"limit": 1, "_request_timeout": (3, 5)}


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_maps_refused_api_access_to_non_retryable_rejection(
    settings: KubernetesParserRuntimeSettings,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
) -> None:
    def refused(*args: object, **kwargs: object) -> None:
        raise ApiException(status=status, reason="private response detail")

    monkeypatch.setattr(client.CoreV1Api, "list_namespaced_pod", refused)
    with pytest.raises(ParserRuntimeRejected, match=f"HTTP {status}") as raised:
        KubernetesParserRuntimeConnection(settings).verify_connection()
    assert "private response detail" not in str(raised.value)


@pytest.mark.parametrize("status", [429, 500, 503])
def test_maps_temporary_api_errors_to_retryable_unavailability(
    settings: KubernetesParserRuntimeSettings,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
) -> None:
    def unavailable(*args: object, **kwargs: object) -> None:
        raise ApiException(status=status, reason="private response detail")

    monkeypatch.setattr(client.CoreV1Api, "list_namespaced_pod", unavailable)
    with pytest.raises(ParserRuntimeUnavailable, match="temporarily unavailable"):
        KubernetesParserRuntimeConnection(settings).verify_connection()


def test_maps_transport_failure_to_retryable_unavailability(
    settings: KubernetesParserRuntimeSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def disconnected(*args: object, **kwargs: object) -> None:
        raise OSError("private network detail")

    monkeypatch.setattr(client.CoreV1Api, "list_namespaced_pod", disconnected)
    with pytest.raises(ParserRuntimeUnavailable, match="temporarily unavailable") as raised:
        KubernetesParserRuntimeConnection(settings).verify_connection()
    assert "private network detail" not in str(raised.value)


def test_maps_tls_failure_to_non_retryable_rejection(
    settings: KubernetesParserRuntimeSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def tls_error(*args: object, **kwargs: object) -> None:
        raise urllib3.exceptions.SSLError("private TLS detail")

    monkeypatch.setattr(client.CoreV1Api, "list_namespaced_pod", tls_error)
    with pytest.raises(ParserRuntimeRejected, match="TLS verification failed"):
        KubernetesParserRuntimeConnection(settings).verify_connection()
