"""Create, run and clean up one isolated Kubernetes parser Job."""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from threading import BoundedSemaphore, Event
from typing import Protocol, cast
from uuid import uuid4

from kubernetes import client
from kubernetes import stream as streaming
from kubernetes.client.exceptions import ApiException
from urllib3.exceptions import HTTPError, SSLError
from websocket import WebSocketException

from document_platform.adapters.outbound.kubernetes.parser_runtime_connection import (
    KubernetesParserRuntimeConnection,
)
from document_platform.application.ports import (
    ParserContainerMemoryLimitExceeded,
    ParserExecutionFailed,
    ParserMemoryLimitExceeded,
    ParserOutputExceeded,
    ParserProcessMemoryLimitExceeded,
    ParserRuntimeRejected,
    ParserRuntimeUnavailable,
)

_REQUEST_TIMEOUT = (3, 5)
_POLL_INTERVAL_SECONDS = 0.2
_STDIN_CHUNK_BYTES = 64 * 1024
_MAX_STDERR_BYTES = 8 * 1024
_MAX_OWNED_PODS = 100
_OOM_COUNTER_OUTPUT_LIMIT = 16
_RUN_LABEL = "parser.platform/run"
_CONTAINER_NAME = "parser"


class _ParserExecOutcomeUnknown(ParserExecutionFailed):
    """Exec ended without a status, so inspect the container before classifying it."""


class ParserOperation(StrEnum):
    EMBEDDED_TEXT = "embedded-text"
    OCR = "ocr"


_OPERATION_ARGUMENTS: dict[ParserOperation, str] = {
    ParserOperation.EMBEDDED_TEXT: "embedded-text",
    ParserOperation.OCR: "ocr",
}
_PARSER_COMMAND = [
    "python",
    "-m",
    "document_platform.parser_worker",
    "--operation",
]
_SUPERVISOR_COMMAND = ["python", "-m", "document_platform.parser_supervisor"]


@dataclass(frozen=True, slots=True)
class KubernetesParserJobSettings:
    image: str
    max_input_bytes: int
    max_output_bytes: int
    cpu_request: str
    cpu_limit: str
    memory_request: str
    memory_limit: str
    ephemeral_storage_request: str
    ephemeral_storage_limit: str
    scratch_limit: str
    active_deadline_seconds: int
    ttl_seconds_after_finished: int
    max_concurrent_jobs: int
    startup_timeout_seconds: float
    execution_timeout_seconds: float
    cleanup_timeout_seconds: float
    max_pages: int = 50
    max_characters: int = 1_000_000
    tesseract_language: str = "eng"
    tesseract_raster_dpi: int = 200
    tesseract_max_page_pixels: int = 20_000_000
    tesseract_page_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.image.strip():
            raise ValueError("image must not be blank")
        for name in (
            "max_input_bytes",
            "max_output_bytes",
            "active_deadline_seconds",
            "max_concurrent_jobs",
            "startup_timeout_seconds",
            "execution_timeout_seconds",
            "cleanup_timeout_seconds",
            "max_pages",
            "max_characters",
            "tesseract_raster_dpi",
            "tesseract_max_page_pixels",
            "tesseract_page_timeout_seconds",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        for name in (
            "cpu_request",
            "cpu_limit",
            "memory_request",
            "memory_limit",
            "ephemeral_storage_request",
            "ephemeral_storage_limit",
            "scratch_limit",
            "tesseract_language",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be blank")
        if self.ttl_seconds_after_finished < 0:
            raise ValueError("ttl_seconds_after_finished must not be negative")
        if not isfinite(self.tesseract_page_timeout_seconds):
            raise ValueError("tesseract_page_timeout_seconds must be finite")
        if not 72 <= self.tesseract_raster_dpi <= 600:
            raise ValueError("tesseract_raster_dpi must be between 72 and 600")


@dataclass(frozen=True, slots=True)
class OwnedParserJob:
    name: str
    uid: str


class _ParserJobCancelled(RuntimeError):
    """Signal the controller thread to delete its Job after activity cancellation."""


class _ExecSocket(Protocol):
    returncode: int | None
    subprotocol: str | None

    def is_open(self) -> bool: ...
    def update(self, timeout: int) -> None: ...
    def read_stdout(self) -> bytes: ...
    def read_stderr(self) -> bytes: ...
    def write_stdin(self, data: bytes) -> None: ...
    def close_channel(self, channel: int) -> None: ...
    def close(self) -> None: ...


class KubernetesParserJobController:
    def __init__(
        self,
        *,
        connection: KubernetesParserRuntimeConnection,
        settings: KubernetesParserJobSettings,
    ) -> None:
        self._connection = connection
        self._settings = settings
        self._capacity = BoundedSemaphore(settings.max_concurrent_jobs)

    def execute(
        self,
        operation: ParserOperation,
        pdf: bytes,
        *,
        cancel_event: Event | None = None,
    ) -> bytes:
        if len(pdf) > self._settings.max_input_bytes:
            raise ParserExecutionFailed("PDF input exceeds the configured byte limit")
        if not self._capacity.acquire(timeout=self._settings.startup_timeout_seconds):
            raise ParserRuntimeUnavailable("Parser runtime is at its concurrency limit")

        name = f"pdf-parser-{operation.value[:8]}-{uuid4().hex[:16]}"
        job: OwnedParserJob | None = None
        pod: str | None = None
        create_attempted = False
        try:
            _raise_if_cancelled(cancel_event)
            create_attempted = True
            created = self._create_job(name)
            job = self._identity(name, created)
            pod = self._wait_for_pod(job, cancel_event=cancel_event)
            oom_kill_baseline = self._read_oom_kill_count(pod)
            try:
                output, exit_code = self._exec(
                    pod,
                    self._parser_command(operation),
                    stdin=pdf,
                    output_limit=self._settings.max_output_bytes,
                    cancel_event=cancel_event,
                )
            except (ApiException, _ParserExecOutcomeUnknown, WebSocketException) as error:
                memory_failure = self._memory_limit_failure(pod, oom_kill_baseline)
                if memory_failure is not None:
                    raise memory_failure from None
                if isinstance(error, ApiException):
                    raise self._api_error(error) from None
                raise
            if exit_code != 0:
                memory_failure = self._memory_limit_failure(pod, oom_kill_baseline)
                if memory_failure is not None:
                    raise memory_failure from None
            _raise_if_cancelled(cancel_event)
            outcome = "success" if exit_code == 0 else "failure"
            _, completion_code = self._exec(
                pod,
                [*_SUPERVISOR_COMMAND, "complete", "--outcome", outcome],
                stdin=None,
                output_limit=1024,
                cancel_event=cancel_event,
            )
            if completion_code != 0:
                raise ParserExecutionFailed("Parser Job completion command failed")
            self._wait_for_terminal(
                job,
                "Complete" if outcome == "success" else "Failed",
                cancel_event=cancel_event,
            )
            if exit_code != 0:
                raise ParserExecutionFailed("Isolated PDF parser returned a failure status")
            return output
        except ApiException as error:
            raise self._api_error(error) from None
        except SSLError:
            raise ParserRuntimeRejected("Kubernetes API TLS verification failed") from None
        except (HTTPError, OSError, WebSocketException):
            raise ParserRuntimeUnavailable(
                "Kubernetes API connection is temporarily unavailable"
            ) from None
        finally:
            try:
                if job is None and create_attempted:
                    job = self._recover_job(name)
                if job is not None:
                    self._cleanup(job)
            finally:
                self._capacity.release()

    def _parser_command(self, operation: ParserOperation) -> list[str]:
        return [
            *_PARSER_COMMAND,
            _OPERATION_ARGUMENTS[operation],
            "--max-input-bytes",
            str(self._settings.max_input_bytes),
            "--max-output-bytes",
            str(self._settings.max_output_bytes),
            "--max-pages",
            str(self._settings.max_pages),
            "--max-characters",
            str(self._settings.max_characters),
            "--tesseract-language",
            self._settings.tesseract_language,
            "--tesseract-raster-dpi",
            str(self._settings.tesseract_raster_dpi),
            "--tesseract-max-page-pixels",
            str(self._settings.tesseract_max_page_pixels),
            "--tesseract-page-timeout-seconds",
            str(self._settings.tesseract_page_timeout_seconds),
        ]

    def _create_job(self, name: str) -> client.V1Job:
        with self._connection.new_api_client() as api:
            return client.BatchV1Api(api).create_namespaced_job(
                self._connection.namespace,
                client.V1Job.model_validate(self._job_manifest(name)),
                _request_timeout=_REQUEST_TIMEOUT,
            )

    def _job_manifest(self, name: str) -> dict[str, object]:
        resources = {
            "requests": {
                "cpu": self._settings.cpu_request,
                "memory": self._settings.memory_request,
                "ephemeral-storage": self._settings.ephemeral_storage_request,
            },
            "limits": {
                "cpu": self._settings.cpu_limit,
                "memory": self._settings.memory_limit,
                "ephemeral-storage": self._settings.ephemeral_storage_limit,
            },
        }
        labels = {_RUN_LABEL: name}
        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"name": name, "labels": labels},
            "spec": {
                "backoffLimit": 0,
                "activeDeadlineSeconds": self._settings.active_deadline_seconds,
                "ttlSecondsAfterFinished": self._settings.ttl_seconds_after_finished,
                "template": {
                    "metadata": {"labels": labels},
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
                                "name": _CONTAINER_NAME,
                                "image": self._settings.image,
                                "imagePullPolicy": "Never",
                                "command": [*_SUPERVISOR_COMMAND, "wait"],
                                "env": [
                                    {"name": "TMPDIR", "value": "/scratch"},
                                    {"name": "TMP", "value": "/scratch"},
                                    {"name": "TEMP", "value": "/scratch"},
                                ],
                                "securityContext": {
                                    "allowPrivilegeEscalation": False,
                                    "readOnlyRootFilesystem": True,
                                    "capabilities": {"drop": ["ALL"]},
                                },
                                "resources": resources,
                                "volumeMounts": [{"name": "scratch", "mountPath": "/scratch"}],
                            }
                        ],
                        "volumes": [
                            {
                                "name": "scratch",
                                "emptyDir": {"sizeLimit": self._settings.scratch_limit},
                            }
                        ],
                    },
                },
            },
        }

    def _identity(self, name: str, job: client.V1Job) -> OwnedParserJob:
        if job.metadata is None or not job.metadata.uid:
            raise ParserRuntimeUnavailable("Kubernetes returned a Job without an identity")
        return OwnedParserJob(name, job.metadata.uid)

    def _recover_job(self, name: str) -> OwnedParserJob | None:
        try:
            with self._connection.new_api_client() as api:
                current = client.BatchV1Api(api).read_namespaced_job(
                    name,
                    self._connection.namespace,
                    _request_timeout=_REQUEST_TIMEOUT,
                )
        except ApiException as error:
            if getattr(error, "status", None) == 404:
                return None
            raise self._api_error(error) from None
        if current.metadata is None or current.metadata.labels is None:
            raise ParserRuntimeRejected("Unacknowledged Job has no ownership label")
        if current.metadata.labels.get(_RUN_LABEL) != name:
            raise ParserRuntimeRejected("Unacknowledged Job has a different owner")
        return self._identity(name, current)

    def _owned_pods(self, core: client.CoreV1Api, job: OwnedParserJob) -> list[client.V1Pod]:
        response = core.list_namespaced_pod(
            self._connection.namespace,
            label_selector=f"batch.kubernetes.io/controller-uid={job.uid}",
            limit=_MAX_OWNED_PODS,
            _request_timeout=_REQUEST_TIMEOUT,
        )
        if response.metadata and response.metadata.var_continue:
            raise ParserRuntimeRejected("Owned parser Pod observation exceeded its limit")
        return [
            pod
            for pod in response.items
            if pod.metadata
            and any(
                owner.uid == job.uid and owner.controller is True
                for owner in pod.metadata.owner_references or []
            )
        ]

    def _wait_for_pod(self, job: OwnedParserJob, *, cancel_event: Event | None = None) -> str:
        deadline = time.monotonic() + self._settings.startup_timeout_seconds
        while time.monotonic() < deadline:
            _raise_if_cancelled(cancel_event)
            with self._connection.new_api_client() as api:
                core = client.CoreV1Api(api)
                for pod in self._owned_pods(core, job):
                    for container in (pod.status.container_statuses or []) if pod.status else []:
                        terminated = container.state.terminated if container.state else None
                        if terminated and terminated.reason == "OOMKilled":
                            raise ParserContainerMemoryLimitExceeded(
                                "Isolated PDF parser container exceeded its memory limit"
                            )
                    if (
                        pod.status
                        and pod.status.phase == "Running"
                        and pod.metadata
                        and pod.metadata.name
                    ):
                        return pod.metadata.name
                    for container in (pod.status.container_statuses or []) if pod.status else []:
                        waiting = container.state.waiting if container.state else None
                        if waiting and waiting.reason in {
                            "ErrImagePull",
                            "ImagePullBackOff",
                            "CreateContainerConfigError",
                        }:
                            raise ParserRuntimeRejected(
                                "Parser Job image or container configuration was rejected"
                            )
                        if container.state and container.state.terminated:
                            raise ParserExecutionFailed("Parser supervisor exited before serving")
            time.sleep(_POLL_INTERVAL_SECONDS)
        raise ParserRuntimeUnavailable("Parser Job did not start before its deadline")

    def _exec(
        self,
        pod: str,
        command: list[str],
        *,
        stdin: bytes | None,
        output_limit: int,
        cancel_event: Event | None = None,
    ) -> tuple[bytes, int]:
        _raise_if_cancelled(cancel_event)
        with self._connection.new_api_client() as api:
            core = client.CoreV1Api(api)
            stream_call = cast(Callable[..., _ExecSocket], streaming.stream)  # pyright: ignore[reportUnknownMemberType]
            websocket = stream_call(
                core.connect_get_namespaced_pod_exec,
                pod,
                self._connection.namespace,
                command=command,
                container=_CONTAINER_NAME,
                stderr=True,
                stdout=True,
                stdin=stdin is not None,
                tty=False,
                binary=True,
                _preload_content=False,
                _request_timeout=_REQUEST_TIMEOUT,
            )
            deadline = time.monotonic() + self._settings.execution_timeout_seconds
            stdout = bytearray()
            stderr_size = 0
            try:
                if stdin is not None:
                    if websocket.subprotocol != "v5.channel.k8s.io":
                        raise ParserRuntimeRejected(
                            "Kubernetes exec does not support closing the stdin channel"
                        )
                    for offset in range(0, len(stdin), _STDIN_CHUNK_BYTES):
                        _raise_if_cancelled(cancel_event)
                        if time.monotonic() >= deadline:
                            raise ParserRuntimeUnavailable("Parser input transfer timed out")
                        websocket.write_stdin(stdin[offset : offset + _STDIN_CHUNK_BYTES])
                    websocket.close_channel(0)
                while websocket.is_open():
                    _raise_if_cancelled(cancel_event)
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ParserRuntimeUnavailable("Parser command exceeded its deadline")
                    websocket.update(timeout=max(1, int(min(1.0, remaining))))
                    if time.monotonic() >= deadline:
                        raise ParserRuntimeUnavailable("Parser command exceeded its deadline")
                    output = websocket.read_stdout()
                    stderr_size += len(websocket.read_stderr())
                    if len(stdout) + len(output) > output_limit:
                        raise ParserOutputExceeded("Parser result exceeded its byte limit")
                    if stderr_size > _MAX_STDERR_BYTES:
                        raise ParserOutputExceeded("Parser stderr exceeded its byte limit")
                    stdout.extend(output)
                try:
                    exit_code = websocket.returncode
                except (KeyError, TypeError, ValueError):
                    raise _ParserExecOutcomeUnknown(
                        "Isolated parser exec terminated without a usable exit status"
                    ) from None
                if not isinstance(exit_code, int):
                    raise _ParserExecOutcomeUnknown("Parser exec returned no exit status")
                return bytes(stdout), exit_code
            finally:
                websocket.close()

    def _read_oom_kill_count(self, pod: str) -> int | None:
        output, exit_code = self._exec(
            pod,
            [*_SUPERVISOR_COMMAND, "oom-count"],
            stdin=None,
            output_limit=_OOM_COUNTER_OUTPUT_LIMIT,
        )
        if exit_code != 0:
            return None
        try:
            count = int(output.decode("ascii").strip())
        except (UnicodeDecodeError, ValueError):
            return None
        return count if count >= 0 else None

    def _memory_limit_failure(
        self, pod: str, baseline: int | None
    ) -> ParserMemoryLimitExceeded | None:
        counter_error: Exception | None = None
        counter_increased = False
        if baseline is not None:
            try:
                current = self._read_oom_kill_count(pod)
            except ApiException as error:
                if getattr(error, "status", None) in {400, 404}:
                    counter_error = None
                else:
                    counter_error = self._api_error(error)
            except (
                _ParserExecOutcomeUnknown,
                ParserRuntimeUnavailable,
                WebSocketException,
            ) as error:
                counter_error = error
            else:
                counter_increased = current is not None and current > baseline
        try:
            container_oom_killed = self._pod_container_oom_killed(pod)
        except (ParserRuntimeRejected, ParserRuntimeUnavailable) as error:
            if counter_increased:
                return ParserMemoryLimitExceeded("Isolated parser cgroup reported an OOM kill")
            raise error
        if container_oom_killed:
            return ParserContainerMemoryLimitExceeded(
                "Isolated PDF parser container exceeded its memory limit"
            )
        if counter_increased:
            return ParserProcessMemoryLimitExceeded(
                "An isolated PDF parser process exceeded its memory limit"
            )
        if counter_error is not None:
            raise counter_error
        return None

    def _pod_container_oom_killed(self, pod_name: str) -> bool:
        deadline = time.monotonic() + min(3.0, self._settings.cleanup_timeout_seconds)
        last_api_error: ParserRuntimeUnavailable | None = None
        while True:
            try:
                with self._connection.new_api_client() as api:
                    pod = client.CoreV1Api(api).read_namespaced_pod(
                        pod_name,
                        self._connection.namespace,
                        _request_timeout=_REQUEST_TIMEOUT,
                    )
            except ApiException as error:
                if getattr(error, "status", None) == 404:
                    return False
                mapped_error = self._api_error(error)
                if not isinstance(mapped_error, ParserRuntimeUnavailable):
                    raise mapped_error from None
                last_api_error = mapped_error
            except SSLError:
                raise ParserRuntimeRejected("Kubernetes API TLS verification failed") from None
            except (HTTPError, OSError):
                last_api_error = ParserRuntimeUnavailable(
                    "Kubernetes API connection is temporarily unavailable"
                )
            else:
                for status in pod.status.container_statuses or [] if pod.status else []:
                    if status.name != _CONTAINER_NAME:
                        continue
                    states = (status.state, status.last_state)
                    if any(
                        state and state.terminated and state.terminated.reason == "OOMKilled"
                        for state in states
                    ):
                        return True
                    if any(state and state.terminated for state in states):
                        return False
                if pod.status and pod.status.phase in {"Failed", "Succeeded"}:
                    return False

            if time.monotonic() >= deadline:
                if last_api_error is not None:
                    raise last_api_error
                return False
            time.sleep(_POLL_INTERVAL_SECONDS)

    def _wait_for_terminal(
        self,
        job: OwnedParserJob,
        expected: str,
        *,
        cancel_event: Event | None = None,
    ) -> None:
        deadline = time.monotonic() + self._settings.execution_timeout_seconds
        while time.monotonic() < deadline:
            _raise_if_cancelled(cancel_event)
            with self._connection.new_api_client() as api:
                current = client.BatchV1Api(api).read_namespaced_job(
                    job.name,
                    self._connection.namespace,
                    _request_timeout=_REQUEST_TIMEOUT,
                )
            if self._identity(job.name, current).uid != job.uid:
                raise ParserRuntimeRejected("Parser Job name was assigned to a different identity")
            if current.status and any(
                condition.type == expected and condition.status == "True"
                for condition in current.status.conditions or []
            ):
                return
            time.sleep(_POLL_INTERVAL_SECONDS)
        raise ParserRuntimeUnavailable("Parser Job did not finish before its deadline")

    def _cleanup(self, job: OwnedParserJob) -> None:
        deadline = time.monotonic() + self._settings.cleanup_timeout_seconds
        try:
            with self._connection.new_api_client() as api:
                batch = client.BatchV1Api(api)
                core = client.CoreV1Api(api)
                try:
                    batch.delete_namespaced_job(
                        job.name,
                        self._connection.namespace,
                        body=client.V1DeleteOptions(
                            propagation_policy="Foreground",
                            preconditions=client.V1Preconditions(uid=job.uid),
                            grace_period_seconds=1,
                        ),
                        _request_timeout=_REQUEST_TIMEOUT,
                    )
                except ApiException as error:
                    if getattr(error, "status", None) != 404:
                        raise self._api_error(error) from None
                while time.monotonic() < deadline:
                    try:
                        current = batch.read_namespaced_job(
                            job.name,
                            self._connection.namespace,
                            _request_timeout=_REQUEST_TIMEOUT,
                        )
                        if self._identity(job.name, current).uid != job.uid:
                            raise ParserRuntimeRejected(
                                "Parser Job name was assigned to a different identity"
                            )
                    except ApiException as error:
                        if getattr(error, "status", None) != 404:
                            raise self._api_error(error) from None
                        if not self._owned_pods(core, job):
                            return
                    time.sleep(_POLL_INTERVAL_SECONDS)
        except SSLError:
            raise ParserRuntimeRejected("Kubernetes API TLS verification failed") from None
        except (HTTPError, OSError):
            raise ParserRuntimeUnavailable(
                "Kubernetes API connection is temporarily unavailable"
            ) from None
        raise ParserRuntimeUnavailable("Parser Job cleanup did not finish before its deadline")

    @staticmethod
    def _api_error(error: ApiException) -> ParserRuntimeRejected | ParserRuntimeUnavailable:
        status = getattr(error, "status", None)
        if status == 403 and KubernetesParserJobController._is_quota_exceeded(error):
            return ParserRuntimeUnavailable("Parser namespace resource quota is exhausted")
        if status == 429 or status is None or status <= 0 or status >= 500:
            return ParserRuntimeUnavailable("Kubernetes API is temporarily unavailable")
        status_code = str(status) if isinstance(status, int) else "unknown"
        return ParserRuntimeRejected(
            f"Kubernetes API refused the parser request (HTTP {status_code})"
        )

    @staticmethod
    def _is_quota_exceeded(error: ApiException) -> bool:
        try:
            payload: object = json.loads(error.body or "")
        except (TypeError, json.JSONDecodeError):
            return False
        if not isinstance(payload, dict):
            return False
        typed_payload = cast(dict[str, object], payload)
        if typed_payload.get("reason") != "Forbidden":
            return False
        message = typed_payload.get("message")
        return isinstance(message, str) and "exceeded quota:" in message.lower()


def _raise_if_cancelled(cancel_event: Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise _ParserJobCancelled("Parser Job cancellation was requested")
