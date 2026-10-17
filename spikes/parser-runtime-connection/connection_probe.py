"""Verify explicit controller connection settings against a disposable local cluster."""

import argparse
import json
import re
import ssl
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from kubernetes import client
from kubernetes.client.exceptions import ApiException
from urllib3.exceptions import HTTPError

REQUEST_TIMEOUT = (3, 5)
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "host.docker.internal"}
RESERVED_NAMESPACES = {"default", "kube-system", "kube-public", "kube-node-lease"}


class ProbeError(Exception):
    """A connection or permission check failed without exposing credentials."""


@dataclass(frozen=True)
class ConnectionSettings:
    endpoint: str
    namespace: str
    ca_file: Path
    token_file: Path

    def __post_init__(self) -> None:
        try:
            endpoint = urlsplit(self.endpoint)
            valid = (
                endpoint.scheme == "https"
                and endpoint.hostname in LOCAL_HOSTS
                and endpoint.port is not None
                and 1 <= endpoint.port <= 65535
                and endpoint.username is None
                and endpoint.password is None
                and endpoint.path in {"", "/"}
                and not endpoint.query
                and not endpoint.fragment
                and not any(character.isspace() for character in self.endpoint)
            )
        except ValueError:
            valid = False
        if not valid:
            raise ProbeError("Use an explicit local HTTPS endpoint with a port and no credentials")
        if (
            self.namespace in RESERVED_NAMESPACES
            or len(self.namespace) > 63
            or re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", self.namespace) is None
        ):
            raise ProbeError("Use a dedicated valid namespace")


def read_token(token_file: Path) -> str:
    try:
        with token_file.open(encoding="ascii") as source:
            token = source.read(16_385).strip()
    except (OSError, UnicodeError):
        raise ProbeError("Controller token file is unreadable") from None
    if not token or len(token) > 16_384 or any(character.isspace() for character in token):
        raise ProbeError("Controller token file must contain one bounded bearer token")
    if any(ord(character) < 33 or ord(character) > 126 for character in token):
        raise ProbeError("Controller token contains invalid characters")
    return token


def build_configuration(settings: ConnectionSettings) -> client.Configuration:
    try:
        ssl.create_default_context(cafile=str(settings.ca_file))
    except (OSError, ssl.SSLError):
        raise ProbeError("Cluster CA file is unreadable or invalid") from None

    configuration = client.Configuration()
    configuration.host = settings.endpoint.rstrip("/")
    configuration.ssl_ca_cert = str(settings.ca_file)
    configuration.verify_ssl = True
    configuration.cert_file = None
    configuration.key_file = None
    configuration.debug = False
    configuration.proxy = None
    configuration.retries = 0
    configuration.api_key = {"authorization": read_token(settings.token_file)}
    configuration.api_key_prefix = {"authorization": "Bearer"}

    def refresh_token(current: client.Configuration) -> None:
        current.api_key["authorization"] = read_token(settings.token_file)

    # The SDK exposes this callback but infers its type only from the initial None value.
    configuration.refresh_api_key_hook = refresh_token  # pyright: ignore[reportAttributeAccessIssue]
    return configuration


def verify_connection(settings: ConnectionSettings) -> dict[str, str]:
    configuration = build_configuration(settings)
    try:
        with client.ApiClient(configuration=configuration) as api:
            client.CoreV1Api(api).list_namespaced_pod(
                settings.namespace, limit=1, _request_timeout=REQUEST_TIMEOUT
            )
            authorization = client.AuthorizationV1Api(api)

            def check(
                group: str,
                resource: str,
                verb: str,
                *,
                namespace: str,
                expected_allowed: bool = True,
            ) -> None:
                resource_name, _, subresource = resource.partition("/")
                review = client.V1SelfSubjectAccessReview(
                    spec=client.V1SelfSubjectAccessReviewSpec(
                        resource_attributes=client.V1ResourceAttributes(
                            group=group,
                            resource=resource_name,
                            subresource=subresource or None,
                            verb=verb,
                            namespace=namespace,
                        )
                    )
                )
                result = authorization.create_self_subject_access_review(
                    review, _request_timeout=REQUEST_TIMEOUT
                )
                if result.status is None or result.status.evaluation_error:
                    raise ProbeError("Kubernetes could not evaluate the permission check")
                allowed = result.status.allowed is True
                if allowed != expected_allowed:
                    raise ProbeError(
                        "Controller RBAC does not match the expected scoped permissions"
                    )

            for verb in ("create", "get", "list", "watch", "delete"):
                check("batch", "jobs", verb, namespace=settings.namespace)
            for verb in ("get", "list", "watch"):
                check("", "pods", verb, namespace=settings.namespace)
            for verb in ("get", "create"):
                check("", "pods/exec", verb, namespace=settings.namespace)
            for verb in ("get", "list"):
                check("", "secrets", verb, namespace=settings.namespace, expected_allowed=False)
            check("", "pods", "create", namespace=settings.namespace, expected_allowed=False)
            check(
                "rbac.authorization.k8s.io",
                "rolebindings",
                "create",
                namespace=settings.namespace,
                expected_allowed=False,
            )
            check("", "pods", "list", namespace="default", expected_allowed=False)
            check("batch", "jobs", "create", namespace="default", expected_allowed=False)
    except ApiException as error:
        status = getattr(error, "status", None)
        status_code = str(status) if isinstance(status, int) else "unknown"
        raise ProbeError(
            f"Kubernetes API refused the connection or check (HTTP {status_code})"
        ) from None
    except (HTTPError, OSError):
        raise ProbeError("TLS verification or network connection failed") from None

    return {"tls": "verified", "required_rbac": "allowed", "checked_denials": "denied"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--ca-file", required=True, type=Path)
    parser.add_argument("--token-file", required=True, type=Path)
    args = parser.parse_args()
    try:
        settings = ConnectionSettings(args.endpoint, args.namespace, args.ca_file, args.token_file)
        result = verify_connection(settings)
    except ProbeError as error:
        print(json.dumps({"result": "failed", "reason": str(error)}), file=sys.stderr)
        return 1
    except Exception:
        print(
            json.dumps({"result": "failed", "reason": "Unexpected Kubernetes client response"}),
            file=sys.stderr,
        )
        return 1
    print(json.dumps({"result": "passed", **result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
