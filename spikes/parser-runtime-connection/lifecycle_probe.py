"""Exercise scoped Job cleanup using synthetic commands, independently of the worker."""

import argparse
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast
from uuid import uuid4

from connection_probe import REQUEST_TIMEOUT, ConnectionSettings, ProbeError, build_configuration
from kubernetes import client
from kubernetes import stream as streaming
from kubernetes.client.exceptions import ApiException

SUPERVISOR = """
import pathlib, time
marker = pathlib.Path('/scratch/outcome')
while not marker.exists():
    time.sleep(0.1)
raise SystemExit(0 if marker.read_text() == 'success' else 1)
"""
PARSER_COMMANDS = {
    "success": "raise SystemExit(0)",
    "error": "raise SystemExit(7)",
    "cancel": (
        "from pathlib import Path; import time; "
        "Path('/scratch/parser-started').touch(); time.sleep(300)"
    ),
    "abandon": (
        "from pathlib import Path; import time; "
        "Path('/scratch/parser-started').touch(); time.sleep(300)"
    ),
}


@dataclass(frozen=True)
class OwnedJob:
    name: str
    uid: str


class ExecSocket(Protocol):
    """The untyped SDK stream wrapper returns this small WebSocket interface."""

    returncode: int | None

    def is_open(self) -> bool: ...
    def update(self, timeout: int) -> None: ...
    def read_stdout(self) -> str: ...
    def read_stderr(self) -> str: ...
    def close(self) -> None: ...


def identity(name: str, job: client.V1Job) -> OwnedJob:
    if job.metadata is None or not job.metadata.uid:
        raise ProbeError("Job response has no UID")
    return OwnedJob(name, job.metadata.uid)


def job_manifest(name: str, image: str) -> dict[str, object]:
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": name, "labels": {"parser-probe/run": name}},
        "spec": {
            "backoffLimit": 0,
            "activeDeadlineSeconds": 60,
            "ttlSecondsAfterFinished": 5,
            "template": {
                "spec": {
                    "automountServiceAccountToken": False,
                    "restartPolicy": "Never",
                    "terminationGracePeriodSeconds": 1,
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": 10001,
                        "runAsGroup": 10001,
                        "fsGroup": 10001,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "containers": [
                        {
                            "name": "parser",
                            "image": image,
                            "imagePullPolicy": "Never",
                            "command": ["python", "-c", SUPERVISOR],
                            "securityContext": {
                                "allowPrivilegeEscalation": False,
                                "readOnlyRootFilesystem": True,
                                "capabilities": {"drop": ["ALL"]},
                            },
                            "resources": {
                                "requests": {"cpu": "100m", "memory": "64Mi"},
                                "limits": {"cpu": "1", "memory": "256Mi"},
                            },
                            "volumeMounts": [{"name": "scratch", "mountPath": "/scratch"}],
                        }
                    ],
                    "volumes": [
                        {"name": "scratch", "emptyDir": {"medium": "Memory", "sizeLimit": "16Mi"}}
                    ],
                }
            },
        },
    }


class LifecycleProbe:
    def __init__(self, settings: ConnectionSettings) -> None:
        self.settings = settings

    def recover_job(self, name: str) -> OwnedJob | None:
        # A timed-out create can still have reached the API server.
        with client.ApiClient(build_configuration(self.settings)) as api:
            try:
                current = client.BatchV1Api(api).read_namespaced_job(
                    name, self.settings.namespace, _request_timeout=REQUEST_TIMEOUT
                )
            except ApiException as error:
                if getattr(error, "status", None) == 404:
                    return None
                raise ProbeError("Unacknowledged Job creation could not be reconciled") from None
            if (
                current.metadata is None
                or (current.metadata.labels or {}).get("parser-probe/run") != name
            ):
                raise ProbeError("Job creation recovery found a different owner")
            return identity(name, current)

    def owned_pods(self, core: client.CoreV1Api, job: OwnedJob) -> list[client.V1Pod]:
        response = core.list_namespaced_pod(
            self.settings.namespace,
            label_selector=f"batch.kubernetes.io/controller-uid={job.uid}",
            limit=100,
            _request_timeout=REQUEST_TIMEOUT,
        )
        if response.metadata and response.metadata.var_continue:
            raise ProbeError("Pod observation exceeded the probe limit")
        return [
            pod
            for pod in response.items
            if pod.metadata
            and any(
                owner.uid == job.uid and owner.controller is True
                for owner in pod.metadata.owner_references or []
            )
        ]

    def cleanup(self, job: OwnedJob, timeout: float = 30) -> None:
        # Exec mutates its ApiClient transport; cleanup must use a fresh REST client.
        with client.ApiClient(build_configuration(self.settings)) as api:
            batch = client.BatchV1Api(api)
            core = client.CoreV1Api(api)
            try:
                batch.delete_namespaced_job(
                    job.name,
                    self.settings.namespace,
                    body=client.V1DeleteOptions(
                        propagation_policy="Foreground",
                        preconditions=client.V1Preconditions(uid=job.uid),
                        grace_period_seconds=1,
                    ),
                    _request_timeout=REQUEST_TIMEOUT,
                )
            except ApiException as error:
                if getattr(error, "status", None) != 404:
                    raise ProbeError("Job deletion was refused or could not be confirmed") from None
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                absent = False
                try:
                    current = batch.read_namespaced_job(
                        job.name, self.settings.namespace, _request_timeout=REQUEST_TIMEOUT
                    )
                    if identity(job.name, current).uid != job.uid:
                        raise ProbeError("Job name now belongs to a different UID")
                except ApiException as error:
                    if getattr(error, "status", None) != 404:
                        raise ProbeError("Job removal could not be observed") from None
                    absent = True
                if absent and not self.owned_pods(core, job):
                    return
                time.sleep(0.2)
        raise ProbeError("Job or owned Pods remained after the cleanup deadline")

    def wait_for_pod(self, job: OwnedJob) -> str:
        with client.ApiClient(build_configuration(self.settings)) as api:
            core = client.CoreV1Api(api)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                for pod in self.owned_pods(core, job):
                    if (
                        pod.status
                        and pod.status.phase == "Running"
                        and pod.metadata
                        and pod.metadata.name
                    ):
                        return pod.metadata.name
                time.sleep(0.2)
        raise ProbeError("Synthetic parser did not start before the deadline")

    def execute(self, pod: str, code: str) -> int:
        with client.ApiClient(build_configuration(self.settings)) as api:
            core = client.CoreV1Api(api)
            # The SDK exposes stream as an untyped functools.partial.
            stream = cast(Callable[..., ExecSocket], streaming.stream)  # pyright: ignore[reportUnknownMemberType]
            websocket = stream(
                core.connect_get_namespaced_pod_exec,
                pod,
                self.settings.namespace,
                command=["python", "-c", code],
                container="parser",
                stderr=True,
                stdout=True,
                stdin=False,
                tty=False,
                _preload_content=False,
                _request_timeout=REQUEST_TIMEOUT,
            )
            deadline = time.monotonic() + 90
            received = 0
            try:
                while websocket.is_open():
                    if time.monotonic() >= deadline:
                        raise ProbeError("Synthetic exec exceeded its deadline")
                    websocket.update(timeout=1)
                    received += len(websocket.read_stdout()) + len(websocket.read_stderr())
                    if received > 8192:
                        raise ProbeError("Synthetic exec exceeded its output limit")
                status = websocket.returncode
                if not isinstance(status, int):
                    raise ProbeError("Synthetic exec did not report an exit status")
                return status
            finally:
                websocket.close()

    def wait_for_terminal(self, job: OwnedJob, expected: str) -> None:
        with client.ApiClient(build_configuration(self.settings)) as api:
            batch = client.BatchV1Api(api)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                current = batch.read_namespaced_job(
                    job.name, self.settings.namespace, _request_timeout=REQUEST_TIMEOUT
                )
                if identity(job.name, current).uid != job.uid:
                    raise ProbeError("Job name now belongs to a different UID")
                if current.status and any(
                    condition.type == expected and condition.status == "True"
                    for condition in current.status.conditions or []
                ):
                    return
                time.sleep(0.2)
        raise ProbeError("Synthetic Job did not reach its expected terminal state")

    def run(self, scenario: str, image: str) -> None:
        name = f"lifecycle-{uuid4().hex[:16]}"
        job = None
        try:
            with client.ApiClient(build_configuration(self.settings)) as api:
                created = client.BatchV1Api(api).create_namespaced_job(
                    self.settings.namespace,
                    client.V1Job.model_validate(job_manifest(name, image)),
                    _request_timeout=REQUEST_TIMEOUT,
                )
            job = identity(name, created)
            pod = self.wait_for_pod(job)
            print(json.dumps({"event": "executing", "scenario": scenario, "job": name}), flush=True)
            status = self.execute(pod, PARSER_COMMANDS[scenario])
            expected = 7 if scenario == "error" else 0
            if status != expected:
                raise ProbeError("Synthetic parser returned an unexpected exit status")
            outcome = "failure" if status else "success"
            marker_code = (
                f"from pathlib import Path; Path('/scratch/outcome').write_text('{outcome}')"
            )
            if self.execute(pod, marker_code) != 0:
                raise ProbeError("Supervisor completion command failed")
            self.wait_for_terminal(job, "Failed" if status else "Complete")
        finally:
            job = job or self.recover_job(name)
            if job is not None:
                self.cleanup(job)
                print(
                    json.dumps({"event": "cleaned", "scenario": scenario, "job": name}), flush=True
                )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--ca-file", required=True, type=Path)
    parser.add_argument("--token-file", required=True, type=Path)
    parser.add_argument("--image", default="document-platform-api:dev")
    parser.add_argument("--scenario", choices=PARSER_COMMANDS, required=True)
    args = parser.parse_args()
    try:
        probe = LifecycleProbe(
            ConnectionSettings(args.endpoint, args.namespace, args.ca_file, args.token_file)
        )
        probe.run(args.scenario, args.image)
    except KeyboardInterrupt:
        print(json.dumps({"event": "cancelled"}), flush=True)
        return 130
    except Exception:
        print(json.dumps({"event": "failed", "reason": "Lifecycle check or cleanup failed"}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
