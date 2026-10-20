"""Bootstrap and supervise the local Kind/Calico PDF parser runtime."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import secrets
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import FrameType

ROOT = Path(__file__).resolve().parents[1]
SPIKE = ROOT / "spikes/parser-runtime-connection"
CLUSTER_NODE_IMAGE = "kindest/node:v1.37.0"
CALICO_VERSION = "v3.33.0"
NAMESPACE = "pdf-parser-probe"
ANCHOR = "parser-controller-session"
PARSER_IMAGE = "document-platform-parser:dev"
APP_IMAGE = "document-platform-api:dev"
CALICO_BASE = f"https://raw.githubusercontent.com/projectcalico/calico/{CALICO_VERSION}/manifests"
CALICO_MANIFESTS = (
    f"{CALICO_BASE}/v3_projectcalico_org.yaml",
    f"{CALICO_BASE}/tigera-operator.yaml",
    f"{CALICO_BASE}/custom-resources.yaml",
)


class ParserRuntimeError(RuntimeError):
    """A bounded, user-safe runtime setup failure."""


def stop_requested(signum: int, frame: FrameType | None) -> None:
    del signum, frame
    raise KeyboardInterrupt


def require_tools(*names: str) -> None:
    missing = [name for name in names if shutil.which(name) is None]
    if missing:
        raise ParserRuntimeError(f"Required local commands are missing: {', '.join(missing)}")


def run(
    command: list[str],
    *,
    capture: bool = False,
    input_text: str | None = None,
    environment: dict[str, str] | None = None,
    check: bool = True,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            input=input_text,
            env=environment,
            text=True,
            capture_output=capture,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ParserRuntimeError(f"Could not run {command[0]} ({type(error).__name__})") from None
    if check and result.returncode:
        raise ParserRuntimeError(f"{command[0]} command failed with exit code {result.returncode}")
    return result


def cleanup_command(
    command: list[str],
    *,
    environment: dict[str, str] | None = None,
    timeout: int,
) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def compose_prefix() -> list[str]:
    return ["docker", "compose", "--profile", "processing"]


def kubectl(kubeconfig: Path, context: str, *arguments: str, input_text: str | None = None) -> str:
    result = run(
        ["kubectl", "--kubeconfig", str(kubeconfig), "--context", context, *arguments],
        capture=True,
        input_text=input_text,
        check=False,
        timeout=240,
    )
    if result.returncode:
        details = result.stderr.strip().splitlines()
        detail = details[-1][:240] if details else "no diagnostic output"
        operation = arguments[0] if arguments else "request"
        raise ParserRuntimeError(
            f"kubectl {operation} failed with exit code {result.returncode}: {detail}"
        )
    return result.stdout


def safe_image_reference(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", value):
        raise ParserRuntimeError("Parser image must be a bounded local Docker image reference")
    return value


def private_run_directory() -> Path:
    parent = Path("/private/tmp")
    if not parent.is_dir():
        parent = Path(tempfile.gettempdir())
    directory = Path(tempfile.mkdtemp(prefix="ai-doc-parser-runtime-", dir=parent))
    directory.chmod(0o700)
    return directory


def compose_environment(
    directory: Path, endpoint: str = "https://host.docker.internal:1"
) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "DOCUMENT_PLATFORM_PARSER_KUBERNETES_ENDPOINT": endpoint,
            "DOCUMENT_PLATFORM_PARSER_KUBERNETES_NAMESPACE": NAMESPACE,
            "DOCUMENT_PLATFORM_PARSER_JOB_IMAGE": PARSER_IMAGE,
            "DOCUMENT_PLATFORM_PARSER_CREDENTIALS_DIR": str(directory / "credentials"),
        }
    )
    return environment


def check_compose_is_stopped(environment: dict[str, str]) -> None:
    result = run(
        [*compose_prefix(), "ps", "--status", "running", "--services"],
        capture=True,
        environment=environment,
        check=False,
    )
    if result.returncode:
        details = result.stderr.strip().splitlines()
        detail = details[-1][:240] if details else "no diagnostic output"
        raise ParserRuntimeError(f"Could not inspect the processing Compose project: {detail}")
    running = [line for line in result.stdout.splitlines() if line.strip()]
    if running:
        raise ParserRuntimeError(
            "Stop the existing processing Compose services before starting this supervised session"
        )


def build_images(environment: dict[str, str], parser_image: str) -> None:
    print("Building the current API/worker image and console image…", flush=True)
    run(
        [*compose_prefix(), "build", "--quiet", "migrate", "console"],
        environment=environment,
        timeout=1800,
    )
    run(["docker", "tag", APP_IMAGE, parser_image], timeout=60)


def install_calico(kubeconfig: Path, context: str) -> None:
    print(f"Installing pinned Calico {CALICO_VERSION.removeprefix('v')}…", flush=True)
    for manifest in CALICO_MANIFESTS:
        kubectl(kubeconfig, context, "create", "-f", manifest)
    kubectl(
        kubeconfig,
        context,
        "rollout",
        "status",
        "deployment/tigera-operator",
        "--namespace=tigera-operator",
        "--timeout=180s",
    )
    wait_for_resource(
        kubeconfig,
        context,
        "daemonset/calico-node",
        namespace="calico-system",
        timeout=180,
    )
    kubectl(
        kubeconfig,
        context,
        "rollout",
        "status",
        "daemonset/calico-node",
        "--namespace=calico-system",
        "--timeout=180s",
    )
    wait_for_resource(
        kubeconfig,
        context,
        "deployment/calico-kube-controllers",
        namespace="calico-system",
        timeout=180,
    )
    kubectl(
        kubeconfig,
        context,
        "rollout",
        "status",
        "deployment/calico-kube-controllers",
        "--namespace=calico-system",
        "--timeout=180s",
    )
    kubectl(
        kubeconfig, context, "wait", "--for=condition=Ready", "nodes", "--all", "--timeout=180s"
    )


def wait_for_resource(
    kubeconfig: Path,
    context: str,
    resource: str,
    *,
    namespace: str,
    timeout: int,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = run(
            [
                "kubectl",
                "--kubeconfig",
                str(kubeconfig),
                "--context",
                context,
                "get",
                resource,
                f"--namespace={namespace}",
                "--ignore-not-found=true",
                "-o",
                "name",
            ],
            capture=True,
            check=False,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return
        time.sleep(2)
    raise ParserRuntimeError(f"Timed out waiting for Calico resource {resource}")


def wait_for_control_plane_api(kubeconfig: Path, context: str) -> None:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        result = run(
            [
                "kubectl",
                "--kubeconfig",
                str(kubeconfig),
                "--context",
                context,
                "get",
                "--raw=/readyz",
            ],
            capture=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip() == "ok":
            return
        time.sleep(2)
    raise ParserRuntimeError("Kubernetes API did not become ready")


def create_baseline_pod(kubeconfig: Path, context: str, parser_image: str) -> None:
    pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": "parser-egress-probe", "namespace": NAMESPACE},
        "spec": {
            "automountServiceAccountToken": False,
            "activeDeadlineSeconds": 180,
            "terminationGracePeriodSeconds": 1,
            "restartPolicy": "Never",
            "securityContext": {
                "runAsNonRoot": True,
                "runAsUser": 10001,
                "runAsGroup": 10001,
                "seccompProfile": {"type": "RuntimeDefault"},
            },
            "containers": [
                {
                    "name": "probe",
                    "image": parser_image,
                    "imagePullPolicy": "Never",
                    "command": ["python", "-c", "import time; time.sleep(3600)"],
                    "securityContext": {
                        "allowPrivilegeEscalation": False,
                        "readOnlyRootFilesystem": True,
                        "capabilities": {"drop": ["ALL"]},
                    },
                    "resources": {
                        "requests": {"cpu": "20m", "memory": "32Mi"},
                        "limits": {"cpu": "100m", "memory": "128Mi"},
                    },
                }
            ],
        },
    }
    kubectl(
        kubeconfig,
        context,
        "apply",
        "-f",
        "-",
        input_text=json.dumps(pod),
    )
    kubectl(
        kubeconfig,
        context,
        "wait",
        "--for=condition=Ready",
        "pod/parser-egress-probe",
        f"--namespace={NAMESPACE}",
        "--timeout=120s",
    )


def probe_egress(kubeconfig: Path, context: str, *, should_connect: bool) -> None:
    if should_connect:
        source = (
            "import json,socket,ssl; "
            "s=socket.create_connection(('1.1.1.1',443),timeout=5); "
            "t=ssl.create_default_context().wrap_socket(s,server_hostname='one.one.one.one'); "
            "print(json.dumps({'tls':t.version()})); t.close()"
        )
    else:
        source = (
            "import socket, ssl, sys\n"
            "try:\n"
            "    s = socket.create_connection(('1.1.1.1', 443), timeout=5)\n"
            "    t = ssl.create_default_context().wrap_socket("
            "s, server_hostname='one.one.one.one')\n"
            "    t.close()\n"
            "    print('egress unexpectedly reachable')\n"
            "    sys.exit(9)\n"
            "except (OSError, ssl.SSLError):\n"
            "    print('egress blocked')"
        )
    result = run(
        [
            "kubectl",
            "--kubeconfig",
            str(kubeconfig),
            "--context",
            context,
            "exec",
            "--namespace",
            NAMESPACE,
            "parser-egress-probe",
            "--",
            "python",
            "-c",
            source,
        ],
        capture=True,
        timeout=30,
        check=False,
    )
    output = result.stdout.strip()
    if should_connect:
        try:
            protocol = json.loads(output)["tls"]
        except (json.JSONDecodeError, KeyError, TypeError):
            raise ParserRuntimeError(
                "Parser Pod did not complete the external TLS baseline"
            ) from None
        if result.returncode or protocol != "TLSv1.3":
            raise ParserRuntimeError("Parser Pod external TLS baseline failed")
        print("External IPv4 TLS baseline passed (1.1.1.1:443, TLS 1.3).", flush=True)
    else:
        if result.returncode or output != "egress blocked":
            raise ParserRuntimeError("Default-deny policy did not block external IPv4 TLS")
        print("Default-deny policy blocked the same external TLS connection.", flush=True)


def verify_network_policy(kubeconfig: Path, context: str, parser_image: str) -> None:
    kubectl(kubeconfig, context, "apply", "-f", str(SPIKE / "controller-rbac.yaml"))
    create_baseline_pod(kubeconfig, context, parser_image)
    probe_egress(kubeconfig, context, should_connect=True)
    kubectl(kubeconfig, context, "apply", "-f", str(SPIKE / "parser-default-deny.yaml"))
    probe_egress(kubeconfig, context, should_connect=False)
    kubectl(
        kubeconfig,
        context,
        "delete",
        "pod/parser-egress-probe",
        f"--namespace={NAMESPACE}",
        "--wait=true",
        "--timeout=30s",
    )


def apply_parser_resource_quota(kubeconfig: Path, context: str) -> None:
    kubectl(kubeconfig, context, "apply", "-f", str(SPIKE / "parser-resource-quota.yaml"))
    quota = json.loads(
        kubectl(
            kubeconfig,
            context,
            "get",
            "resourcequota",
            "parser-job-budget",
            f"--namespace={NAMESPACE}",
            "-o",
            "json",
        )
    )
    expected = {
        "requests.cpu": "500m",
        "requests.memory": "1Gi",
        "limits.cpu": "2",
        "limits.memory": "2Gi",
        "requests.ephemeral-storage": "128Mi",
        "limits.ephemeral-storage": "256Mi",
    }
    if quota.get("spec", {}).get("hard") != expected:
        raise ParserRuntimeError(
            "Parser namespace resource quota does not match the configured job budget"
        )
    print("Applied the aggregate parser Job resource quota.", flush=True)


def cluster_endpoint_and_ca(
    kubeconfig: Path, context: str, credential_dir: Path
) -> tuple[str, str]:
    configuration = json.loads(
        kubectl(kubeconfig, context, "config", "view", "--raw", "--minify", "-o", "json")
    )
    cluster = configuration["clusters"][0]["cluster"]
    endpoint = cluster.get("server")
    authority = cluster.get("certificate-authority-data")
    match = re.fullmatch(r"https://127\.0\.0\.1:([0-9]{1,5})", endpoint or "")
    if match is None or int(match.group(1)) > 65535 or not authority:
        raise ParserRuntimeError("Kind returned an unexpected local TLS endpoint")
    ca_path = credential_dir / "ca.pem"
    ca_path.write_bytes(base64.b64decode(authority, validate=True))
    ca_path.chmod(0o600)
    return endpoint, f"https://host.docker.internal:{match.group(1)}"


def provision_anchor(kubeconfig: Path, context: str) -> str:
    kubectl(kubeconfig, context, "apply", "-f", str(SPIKE / "credential-anchor.yaml"))
    uid = kubectl(
        kubeconfig,
        context,
        "get",
        "secret",
        ANCHOR,
        f"--namespace={NAMESPACE}",
        "-o",
        "jsonpath={.metadata.uid}",
    ).strip()
    if not re.fullmatch(r"[0-9a-f-]{36}", uid):
        raise ParserRuntimeError("Kubernetes did not return a valid credential anchor UID")
    return uid


def issuer_command(kubeconfig: Path, context: str, credential_dir: Path, uid: str) -> list[str]:
    return [
        "uv",
        "run",
        "--no-sync",
        "python",
        "spikes/parser-runtime-connection/credential_issuer.py",
        "--kubeconfig",
        str(kubeconfig),
        "--context",
        context,
        "--credential-dir",
        str(credential_dir),
        "--bound-uid",
        uid,
    ]


def issue_and_verify(
    kubeconfig: Path,
    context: str,
    credential_dir: Path,
    uid: str,
    endpoint: str,
) -> None:
    run(issuer_command(kubeconfig, context, credential_dir, uid), timeout=20)
    run(
        [
            "uv",
            "run",
            "--no-sync",
            "python",
            "spikes/parser-runtime-connection/connection_probe.py",
            "--endpoint",
            endpoint,
            "--namespace",
            NAMESPACE,
            "--ca-file",
            str(credential_dir / "ca.pem"),
            "--token-file",
            str(credential_dir / "token"),
        ],
        timeout=30,
    )


def wait_for_renewal_events(process: subprocess.Popen[str], expected: int, timeout: float) -> None:
    if process.stdout is None:
        raise ParserRuntimeError("Issuer renewal output is unavailable")
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout
    renewed = 0
    try:
        while renewed < expected:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ParserRuntimeError("Credential issuer did not complete its renewal probe")
            if not selector.select(remaining):
                continue
            line = process.stdout.readline()
            try:
                event = json.loads(line).get("event")
            except (json.JSONDecodeError, AttributeError):
                event = None
            if event == "renewed":
                renewed += 1
            elif event == "failed":
                raise ParserRuntimeError("Credential issuer failed during its renewal probe")
            if process.poll() is not None and renewed < expected:
                raise ParserRuntimeError("Credential issuer exited during its renewal probe")
    finally:
        selector.close()


def start_issuer_watch(command: list[str], *, accelerated: bool = False) -> subprocess.Popen[str]:
    arguments = [*command, "--watch"]
    if accelerated:
        arguments.extend(["--ttl", "600", "--renew-before", "598"])
    return subprocess.Popen(
        arguments,
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE if accelerated else None,
        stderr=subprocess.STDOUT if accelerated else None,
        text=True,
    )


def stop_issuer(process: subprocess.Popen[str] | None, credential_dir: Path) -> None:
    token_path = credential_dir / "token"
    if process is None:
        token_path.unlink(missing_ok=True)
        return
    if process.poll() is None:
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    if token_path.exists():
        raise ParserRuntimeError("Credential issuer did not remove its local token on shutdown")


def delete_owned_cluster(cluster_name: str) -> None:
    known_clusters = cleanup_command(["kind", "get", "clusters"], timeout=30)
    if known_clusters is None or known_clusters.returncode:
        raise ParserRuntimeError("Could not inspect Kind before cleanup")
    if cluster_name not in known_clusters.stdout.splitlines():
        return
    result = cleanup_command(
        ["kind", "delete", "cluster", "--name", cluster_name],
        timeout=120,
    )
    if result is None or result.returncode:
        raise ParserRuntimeError("The dedicated Kind cluster could not be removed")

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        known_clusters = cleanup_command(["kind", "get", "clusters"], timeout=30)
        if known_clusters is None or known_clusters.returncode:
            raise ParserRuntimeError("Could not verify removal of the dedicated Kind cluster")
        if cluster_name not in known_clusters.stdout.splitlines():
            return
        time.sleep(0.5)
    raise ParserRuntimeError("The dedicated Kind cluster remained after deletion")


def clean_runtime(
    *,
    kubeconfig: Path | None,
    context: str | None,
    cluster_name: str | None,
    created_cluster: bool,
    directory: Path,
    issuer: subprocess.Popen[str] | None,
    compose_started: bool,
    compose_environment_values: dict[str, str] | None,
) -> None:
    credential_dir = directory / "credentials"
    cleanup_errors: list[str] = []
    compose_base = compose_prefix()
    if compose_started and compose_environment_values is not None:
        stop_groups = (
            ("api", "console", "temporal-ui", "dispatcher"),
            ("worker",),
            ("temporal", "temporal-postgres", "postgres"),
        )
        stop_timeouts = (30, 180, 60)
        for services, stop_timeout in zip(stop_groups, stop_timeouts, strict=True):
            result = cleanup_command(
                [
                    *compose_base,
                    "stop",
                    "--timeout",
                    str(stop_timeout),
                    *services,
                ],
                environment=compose_environment_values,
                timeout=stop_timeout + 30,
            )
            if result is None or result.returncode:
                cleanup_errors.append(
                    f"Compose services did not stop cleanly: {', '.join(services)}"
                )
    try:
        stop_issuer(issuer, credential_dir)
    except ParserRuntimeError as error:
        cleanup_errors.append(str(error))
    if compose_started and compose_environment_values is not None:
        token_check = [
            *compose_base,
            "exec",
            "-T",
            "parser-credential-sync",
            "python",
            "-c",
            "from pathlib import Path\n"
            "raise SystemExit(Path('/run/parser-runtime/token').exists())",
        ]
        deadline = time.monotonic() + 12
        scrubbed = False
        result: subprocess.CompletedProcess[str] | None = None
        while time.monotonic() < deadline:
            result = cleanup_command(
                token_check,
                environment=compose_environment_values,
                timeout=15,
            )
            if result is None:
                break
            if result.returncode == 0:
                scrubbed = True
                break
            if 'service "parser-credential-sync" is not running' in result.stderr:
                break
            time.sleep(0.5)
        if (
            not scrubbed
            and result is not None
            and result.returncode != 0
            and 'service "parser-credential-sync" is not running' not in result.stderr
        ):
            cleanup_errors.append("The worker credential volume could not be confirmed scrubbed")
        result = cleanup_command(
            [*compose_base, "stop", "parser-credential-sync"],
            environment=compose_environment_values,
            timeout=30,
        )
        if result is None or result.returncode:
            cleanup_errors.append("The credential sync service did not stop cleanly")
    if (
        created_cluster
        and kubeconfig is not None
        and context is not None
        and cluster_name is not None
    ):
        known_clusters = cleanup_command(
            ["kind", "get", "clusters"],
            timeout=30,
        )
        if known_clusters is None or known_clusters.returncode:
            cleanup_errors.append("Could not inspect Kind before cleanup")
        elif cluster_name in known_clusters.stdout.splitlines():
            try:
                kubectl(
                    kubeconfig,
                    context,
                    "delete",
                    "jobs",
                    "--all",
                    f"--namespace={NAMESPACE}",
                    "--wait=true",
                    "--timeout=30s",
                )
                kubectl(
                    kubeconfig,
                    context,
                    "delete",
                    "secret",
                    ANCHOR,
                    f"--namespace={NAMESPACE}",
                    "--ignore-not-found=true",
                    "--wait=true",
                    "--timeout=10s",
                )
            except ParserRuntimeError:
                cleanup_errors.append("Kubernetes cleanup could not be fully confirmed")
            try:
                delete_owned_cluster(cluster_name)
            except ParserRuntimeError as error:
                cleanup_errors.append(str(error))
    if directory.exists() and directory.parent in {
        Path("/private/tmp"),
        Path(tempfile.gettempdir()),
    }:
        shutil.rmtree(directory, ignore_errors=True)
    if cleanup_errors:
        raise ParserRuntimeError("; ".join(cleanup_errors))


def bootstrap(parser_image: str, *, with_compose: bool) -> int:
    require_tools("docker", "kind", "kubectl", "uv")
    parser_image = safe_image_reference(parser_image)
    directory = private_run_directory()
    credential_dir = directory / "credentials"
    credential_dir.mkdir(mode=0o700)
    kubeconfig = directory / "admin.kubeconfig"
    suffix = secrets.token_hex(4)
    cluster_name = f"ai-doc-parser-runtime-{suffix}"
    context = f"kind-{cluster_name}"
    created_cluster = False
    issuer: subprocess.Popen[str] | None = None
    compose_started = False
    compose_env = compose_environment(directory)
    compose_process: subprocess.Popen[bytes] | None = None
    outcome = 1
    try:
        if with_compose:
            check_compose_is_stopped(compose_env)
            build_images(compose_env, parser_image)
        else:
            run(["docker", "image", "inspect", parser_image], capture=True, timeout=30)
        existing = run(["kind", "get", "clusters"], capture=True, timeout=30)
        if cluster_name in existing.stdout.splitlines() or cluster_name == "hub":
            raise ParserRuntimeError("Generated Kind cluster name already exists; refusing reuse")
        created_cluster = True
        run(
            [
                "kind",
                "create",
                "cluster",
                "--name",
                cluster_name,
                "--config",
                str(SPIKE / "kind-container.yaml"),
                "--image",
                CLUSTER_NODE_IMAGE,
                "--kubeconfig",
                str(kubeconfig),
            ],
            timeout=240,
        )
        wait_for_control_plane_api(kubeconfig, context)
        install_calico(kubeconfig, context)
        run(["kind", "load", "docker-image", parser_image, "--name", cluster_name], timeout=180)
        verify_network_policy(kubeconfig, context, parser_image)
        apply_parser_resource_quota(kubeconfig, context)

        host_endpoint, compose_endpoint = cluster_endpoint_and_ca(
            kubeconfig, context, credential_dir
        )
        uid = provision_anchor(kubeconfig, context)
        issue_and_verify(kubeconfig, context, credential_dir, uid, host_endpoint)
        print("Verified the host TLS connection and namespace-scoped controller RBAC.", flush=True)

        if not with_compose:
            renewal = start_issuer_watch(
                issuer_command(kubeconfig, context, credential_dir, uid), accelerated=True
            )
            try:
                wait_for_renewal_events(renewal, expected=2, timeout=15)
                print("Credential issuer completed two renewals in watch mode.", flush=True)
            finally:
                stop_issuer(renewal, credential_dir)
            print("Bootstrap, egress denial, RBAC, TLS and issuer supervision passed.", flush=True)
            outcome = 0
            return outcome

        issuer = start_issuer_watch(issuer_command(kubeconfig, context, credential_dir, uid))
        compose_env = compose_environment(directory, compose_endpoint)
        compose_env["DOCUMENT_PLATFORM_PARSER_JOB_IMAGE"] = parser_image
        run(
            [*compose_prefix(), "config", "--quiet"],
            capture=True,
            environment=compose_env,
            timeout=60,
        )
        print(
            "Starting the processing Compose profile. Press Ctrl-C to stop this session.",
            flush=True,
        )
        compose_process = subprocess.Popen(
            [*compose_prefix(), "up"],
            cwd=ROOT,
            env=compose_env,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        compose_started = True
        while (compose_result := compose_process.poll()) is None:
            if issuer.poll() is not None:
                raise ParserRuntimeError("Host credential issuer exited; stopping Compose")
            time.sleep(0.5)
        outcome = compose_result
        return outcome
    finally:
        try:
            clean_runtime(
                kubeconfig=kubeconfig,
                context=context,
                cluster_name=cluster_name,
                created_cluster=created_cluster,
                directory=directory,
                issuer=issuer,
                compose_started=compose_started,
                compose_environment_values=compose_env if compose_started else None,
            )
        finally:
            if compose_process is not None and compose_process.poll() is None:
                try:
                    compose_process.send_signal(signal.SIGINT)
                    compose_process.wait(timeout=30)
                except (OSError, subprocess.TimeoutExpired):
                    compose_process.terminate()
                    try:
                        compose_process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        compose_process.kill()
                        compose_process.wait(timeout=5)
            if created_cluster:
                delete_owned_cluster(cluster_name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("verify", "up"),
        help="verify creates and removes a disposable cluster; up supervises Compose until stopped",
    )
    parser.add_argument("--parser-image", default=PARSER_IMAGE)
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, stop_requested)
    try:
        return bootstrap(args.parser_image, with_compose=args.action == "up")
    except ParserRuntimeError as error:
        print(f"Parser runtime setup failed: {error}", file=sys.stderr, flush=True)
        return 1
    except KeyboardInterrupt:
        print(
            "Parser runtime session interrupted; cleaning up its dedicated resources.", flush=True
        )
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
