"""Explicit, namespace-scoped Kubernetes API connection for parser jobs."""

import re
import ssl
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from kubernetes import client
from kubernetes.client.exceptions import ApiException
from urllib3.exceptions import HTTPError, SSLError

from document_platform.application.ports import ParserRuntimeRejected, ParserRuntimeUnavailable

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "host.docker.internal"}
_RESERVED_NAMESPACES = {"default", "kube-system", "kube-public", "kube-node-lease"}
_REQUEST_TIMEOUT = (3, 5)
_MAX_TOKEN_BYTES = 16_384


@dataclass(frozen=True, slots=True)
class KubernetesParserRuntimeSettings:
    endpoint: str
    namespace: str
    ca_file: Path
    token_file: Path

    def __post_init__(self) -> None:
        try:
            endpoint = urlsplit(self.endpoint)
            valid_endpoint = (
                endpoint.scheme == "https"
                and endpoint.hostname in _LOCAL_HOSTS
                and endpoint.port is not None
                and 1 <= endpoint.port <= 65_535
                and endpoint.username is None
                and endpoint.password is None
                and endpoint.path in {"", "/"}
                and not endpoint.query
                and not endpoint.fragment
                and not any(character.isspace() for character in self.endpoint)
            )
        except ValueError:
            valid_endpoint = False
        if not valid_endpoint:
            raise ParserRuntimeRejected("Use an explicit local HTTPS parser endpoint with a port")
        if (
            self.namespace in _RESERVED_NAMESPACES
            or len(self.namespace) > 63
            or re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", self.namespace) is None
        ):
            raise ParserRuntimeRejected("Use a dedicated valid parser namespace")


class KubernetesParserRuntimeConnection:
    def __init__(self, settings: KubernetesParserRuntimeSettings) -> None:
        self._settings = settings

    @property
    def namespace(self) -> str:
        return self._settings.namespace

    def new_api_client(self) -> client.ApiClient:
        configuration = self._new_configuration()
        return client.ApiClient(configuration=configuration)

    def verify_connection(self) -> None:
        try:
            with self.new_api_client() as api:
                client.CoreV1Api(api).list_namespaced_pod(
                    self._settings.namespace,
                    limit=1,
                    _request_timeout=_REQUEST_TIMEOUT,
                )
        except ApiException as error:
            status = getattr(error, "status", None)
            if status == 429 or status is None or status >= 500:
                raise ParserRuntimeUnavailable(
                    "Kubernetes API is temporarily unavailable"
                ) from None
            status_code = str(status) if isinstance(status, int) else "unknown"
            raise ParserRuntimeRejected(
                f"Kubernetes API refused the parser controller request (HTTP {status_code})"
            ) from None
        except SSLError:
            raise ParserRuntimeRejected("Kubernetes API TLS verification failed") from None
        except (HTTPError, OSError):
            raise ParserRuntimeUnavailable(
                "Kubernetes API connection is temporarily unavailable"
            ) from None

    def _new_configuration(self) -> client.Configuration:
        try:
            ssl.create_default_context(cafile=str(self._settings.ca_file))
        except (OSError, ssl.SSLError):
            raise ParserRuntimeRejected("Kubernetes CA file is unreadable or invalid") from None

        configuration = client.Configuration()
        configuration.host = self._settings.endpoint.rstrip("/")
        configuration.ssl_ca_cert = str(self._settings.ca_file)
        configuration.verify_ssl = True
        configuration.cert_file = None
        configuration.key_file = None
        configuration.debug = False
        configuration.proxy = None
        configuration.retries = 0
        configuration.api_key = {"authorization": self._read_token()}
        configuration.api_key_prefix = {"authorization": "Bearer"}

        def refresh_token(current: client.Configuration) -> None:
            current.api_key["authorization"] = self._read_token()

        # The Kubernetes SDK infers the callback type from its initial None value.
        configuration.refresh_api_key_hook = refresh_token  # pyright: ignore[reportAttributeAccessIssue]
        return configuration

    def _read_token(self) -> str:
        try:
            with self._settings.token_file.open(encoding="ascii") as source:
                token = source.read(_MAX_TOKEN_BYTES + 1).strip()
        except (OSError, UnicodeError):
            raise ParserRuntimeRejected("Kubernetes controller token file is unreadable") from None
        if (
            not token
            or len(token) > _MAX_TOKEN_BYTES
            or any(
                character.isspace() or ord(character) < 33 or ord(character) > 126
                for character in token
            )
        ):
            raise ParserRuntimeRejected("Kubernetes controller token file is invalid")
        return token
