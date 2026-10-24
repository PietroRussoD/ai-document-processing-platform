"""Restricted Kubernetes Job controller tests."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from threading import Event
from typing import Any, cast
from unittest.mock import Mock

import pytest
from kubernetes import client
from kubernetes.client.exceptions import ApiException
from websocket import WebSocketConnectionClosedException

import document_platform.adapters.outbound.kubernetes.parser_job_controller as controller_module
from document_platform.adapters.outbound.kubernetes import (
    KubernetesParserJobController,
    KubernetesParserJobSettings,
    KubernetesParserRuntimeConnection,
    KubernetesParserRuntimeSettings,
    ParserOperation,
)
from document_platform.application.ports import (
    ParserContainerMemoryLimitExceeded,
    ParserExecutionFailed,
    ParserOutputExceeded,
    ParserProcessMemoryLimitExceeded,
    ParserRuntimeRejected,
    ParserRuntimeUnavailable,
)


class FakeExecSocket:
    def __init__(self, stdout: bytes = b"", returncode: int = 0) -> None:
        self.returncode = returncode
        self.subprotocol = "v5.channel.k8s.io"
        self.stdout = stdout
        self.input = bytearray()
        self.closed_channels: list[int] = []
        self.closed = False

    def is_open(self) -> bool:
        return not self.closed

    def update(self, timeout: int) -> None:
        self.closed = True

    def read_stdout(self) -> bytes:
        output, self.stdout = self.stdout, b""
        return output

    def read_stderr(self) -> bytes:
        return b""

    def write_stdin(self, data: bytes) -> None:
        self.input.extend(data)

    def close_channel(self, channel: int) -> None:
        self.closed_channels.append(channel)

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def controller(tmp_path: Path) -> KubernetesParserJobController:
    token_file = tmp_path / "token"
    token_file.write_text("synthetic-controller-token")
    ca_file = tmp_path / "ca.pem"
    ca_file.write_text("synthetic CA fixture")
    connection = KubernetesParserRuntimeConnection(
        KubernetesParserRuntimeSettings("https://127.0.0.1:6443", "pdf-parser", ca_file, token_file)
    )
    return KubernetesParserJobController(
        connection=connection,
        settings=KubernetesParserJobSettings(
            image="document-platform-parser:dev",
            max_input_bytes=20 * 1024 * 1024,
            max_output_bytes=1_000_100,
            cpu_request="250m",
            cpu_limit="1",
            memory_request="512Mi",
            memory_limit="1Gi",
            ephemeral_storage_request="64Mi",
            ephemeral_storage_limit="128Mi",
            scratch_limit="64Mi",
            active_deadline_seconds=180,
            ttl_seconds_after_finished=60,
            max_concurrent_jobs=2,
            startup_timeout_seconds=30,
            execution_timeout_seconds=120,
            cleanup_timeout_seconds=30,
        ),
    )


def test_job_manifest_enforces_restricted_security_and_bounded_resources(
    controller: KubernetesParserJobController,
) -> None:
    manifest = cast(
        dict[str, Any], cast(Any, controller)._job_manifest("pdf-parser-embedded-1234567890abcdef")
    )
    spec = cast(dict[str, Any], manifest["spec"])
    template = cast(dict[str, Any], spec["template"])
    pod_spec = cast(dict[str, Any], template["spec"])
    container = pod_spec["containers"][0]
    assert container["securityContext"] == {
        "allowPrivilegeEscalation": False,
        "readOnlyRootFilesystem": True,
        "capabilities": {"drop": ["ALL"]},
    }
    assert pod_spec["securityContext"]["runAsUser"] == 10001
    assert pod_spec["securityContext"]["seccompProfile"] == {"type": "RuntimeDefault"}
    assert pod_spec["automountServiceAccountToken"] is False
    assert pod_spec["restartPolicy"] == "Never"
    assert pod_spec["volumes"] == [{"name": "scratch", "emptyDir": {"sizeLimit": "64Mi"}}]
    assert container["resources"]["limits"] == {
        "cpu": "1",
        "memory": "1Gi",
        "ephemeral-storage": "128Mi",
    }
    assert "hostPath" not in str(manifest)
    assert "serviceAccountName" not in pod_spec


def test_rejects_invalid_job_limits() -> None:
    with pytest.raises(ValueError, match="max_output_bytes must be positive"):
        KubernetesParserJobSettings(
            image="parser:dev",
            max_input_bytes=10,
            max_output_bytes=0,
            cpu_request="1",
            cpu_limit="1",
            memory_request="1Gi",
            memory_limit="1Gi",
            ephemeral_storage_request="1Mi",
            ephemeral_storage_limit="1Mi",
            scratch_limit="1Mi",
            active_deadline_seconds=10,
            ttl_seconds_after_finished=1,
            max_concurrent_jobs=1,
            startup_timeout_seconds=1,
            execution_timeout_seconds=1,
            cleanup_timeout_seconds=1,
        )


def test_rejects_an_input_over_the_configured_limit(
    controller: KubernetesParserJobController, monkeypatch: pytest.MonkeyPatch
) -> None:
    create = Mock()
    monkeypatch.setattr(controller, "_create_job", create)
    with pytest.raises(ParserExecutionFailed, match="input exceeds"):
        controller.execute(ParserOperation.EMBEDDED_TEXT, b"x" * (20 * 1024 * 1024 + 1))
    create.assert_not_called()


def test_parser_command_receives_all_configured_limits(
    controller: KubernetesParserJobController,
) -> None:
    command = cast(Any, controller)._parser_command(ParserOperation.OCR)

    assert command[command.index("--operation") + 1] == "ocr"
    assert command[command.index("--max-input-bytes") + 1] == str(20 * 1024 * 1024)
    assert command[command.index("--max-output-bytes") + 1] == "1000100"
    assert command[command.index("--max-pages") + 1] == "50"
    assert command[command.index("--max-characters") + 1] == "1000000"
    assert command[command.index("--tesseract-language") + 1] == "eng"
    assert command[command.index("--tesseract-raster-dpi") + 1] == "200"
    assert command[command.index("--tesseract-max-page-pixels") + 1] == "20000000"
    assert command[command.index("--tesseract-page-timeout-seconds") + 1] == "30.0"


def test_exec_streams_binary_input_in_chunks_and_returns_bounded_output(
    controller: KubernetesParserJobController, monkeypatch: pytest.MonkeyPatch
) -> None:
    socket = FakeExecSocket(stdout=b'{"protocol_version":1}')
    captured: dict[str, Any] = {}

    def stream_call(*args: object, **kwargs: object) -> FakeExecSocket:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return socket

    connection = cast(Any, controller)._connection
    monkeypatch.setattr(connection, "new_api_client", lambda: nullcontext(object()))

    class FakeCoreApi:
        def connect_get_namespaced_pod_exec(self, *args: object, **kwargs: object) -> None:
            return None

    def core_api(api: Any) -> FakeCoreApi:
        return FakeCoreApi()

    monkeypatch.setattr(controller_module.client, "CoreV1Api", core_api)
    monkeypatch.setattr(controller_module.streaming, "stream", stream_call)

    payload = b"pdf-content" * 20_000
    output, exit_code = cast(Any, controller)._exec(
        "synthetic-pod",
        ["python", "-m", "document_platform.parser_worker", "--operation", "ocr"],
        stdin=payload,
        output_limit=100,
    )

    assert bytes(socket.input) == payload
    assert socket.closed_channels == [0]
    assert socket.closed
    assert output == b'{"protocol_version":1}'
    assert exit_code == 0
    assert captured["kwargs"]["binary"] is True
    assert captured["kwargs"]["stdin"] is True
    assert captured["kwargs"]["tty"] is False
    assert captured["kwargs"]["command"][-1] == "ocr"


def test_exec_checks_cancellation_before_opening_websocket(
    controller: KubernetesParserJobController, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = Event()
    event.set()
    stream_call = Mock()
    monkeypatch.setattr(controller_module.streaming, "stream", stream_call)

    with pytest.raises(RuntimeError, match="Parser Job cancellation was requested"):
        cast(Any, controller)._exec(
            "pod",
            ["python"],
            stdin=b"pdf",
            output_limit=100,
            cancel_event=event,
        )

    stream_call.assert_not_called()


def test_exec_enforces_deadline_after_websocket_update(
    controller: KubernetesParserJobController, monkeypatch: pytest.MonkeyPatch
) -> None:
    socket = FakeExecSocket()
    connection = cast(Any, controller)._connection
    monkeypatch.setattr(connection, "new_api_client", lambda: nullcontext(object()))

    class FakeCoreApi:
        def connect_get_namespaced_pod_exec(self, *args: object, **kwargs: object) -> None:
            return None

    def fake_core_api(_api: object) -> FakeCoreApi:
        return FakeCoreApi()

    def fake_stream(*args: Any, **kwargs: Any) -> FakeExecSocket:
        return socket

    monkeypatch.setattr(controller_module.client, "CoreV1Api", fake_core_api)
    monkeypatch.setattr(controller_module.streaming, "stream", fake_stream)
    monotonic = Mock(side_effect=[0.0, 0.0, 121.0])
    monkeypatch.setattr(controller_module.time, "monotonic", monotonic)

    with pytest.raises(ParserRuntimeUnavailable, match="command exceeded its deadline"):
        cast(Any, controller)._exec("pod", ["python"], stdin=None, output_limit=100)

    assert socket.closed


def test_refuses_binary_transfer_without_stdin_half_close_support(
    controller: KubernetesParserJobController, monkeypatch: pytest.MonkeyPatch
) -> None:
    socket = FakeExecSocket()
    socket.subprotocol = "v4.channel.k8s.io"
    connection = cast(Any, controller)._connection
    monkeypatch.setattr(connection, "new_api_client", lambda: nullcontext(object()))

    class FakeCoreApi:
        def connect_get_namespaced_pod_exec(self, *args: object, **kwargs: object) -> None:
            return None

    def core_api(api: Any) -> FakeCoreApi:
        return FakeCoreApi()

    def stream_call(*args: object, **kwargs: object) -> FakeExecSocket:
        return socket

    monkeypatch.setattr(controller_module.client, "CoreV1Api", core_api)
    monkeypatch.setattr(controller_module.streaming, "stream", stream_call)

    with pytest.raises(ParserRuntimeRejected, match="closing the stdin channel"):
        cast(Any, controller)._exec("pod", ["python"], stdin=b"pdf", output_limit=100)
    assert not socket.input
    assert socket.closed


def test_exec_stops_when_stdout_exceeds_its_byte_limit(
    controller: KubernetesParserJobController, monkeypatch: pytest.MonkeyPatch
) -> None:
    socket = FakeExecSocket(stdout=b"x" * 11)
    connection = cast(Any, controller)._connection
    monkeypatch.setattr(connection, "new_api_client", lambda: nullcontext(object()))

    class FakeCoreApi:
        def connect_get_namespaced_pod_exec(self, *args: object, **kwargs: object) -> None:
            return None

    def core_api(api: Any) -> FakeCoreApi:
        return FakeCoreApi()

    def stream_call(*args: object, **kwargs: object) -> FakeExecSocket:
        return socket

    monkeypatch.setattr(controller_module.client, "CoreV1Api", core_api)
    monkeypatch.setattr(controller_module.streaming, "stream", stream_call)

    with pytest.raises(ParserOutputExceeded, match="result exceeded"):
        cast(Any, controller)._exec("pod", ["python"], stdin=b"pdf", output_limit=10)
    assert socket.closed


def test_exec_maps_malformed_runtime_exit_status_to_bounded_parser_failure(
    controller: KubernetesParserJobController, monkeypatch: pytest.MonkeyPatch
) -> None:
    class InvalidReturnCodeSocket(FakeExecSocket):
        def __init__(self) -> None:
            self.subprotocol = "v5.channel.k8s.io"
            self.stdout = b""
            self.input = bytearray()
            self.closed_channels = []
            self.closed = False

        @property
        def returncode(self) -> int:
            raise ValueError("raw runtime detail")

    socket = InvalidReturnCodeSocket()
    connection = cast(Any, controller)._connection
    monkeypatch.setattr(connection, "new_api_client", lambda: nullcontext(object()))

    class FakeCoreApi:
        def connect_get_namespaced_pod_exec(self, *args: object, **kwargs: object) -> None:
            return None

    def fake_core_api(_api: object) -> FakeCoreApi:
        return FakeCoreApi()

    def fake_stream(*args: Any, **kwargs: Any) -> FakeExecSocket:
        return socket

    monkeypatch.setattr(controller_module.client, "CoreV1Api", fake_core_api)
    monkeypatch.setattr(controller_module.streaming, "stream", fake_stream)

    with pytest.raises(ParserExecutionFailed, match="without a usable exit status") as raised:
        cast(Any, controller)._exec("pod", ["python"], stdin=None, output_limit=100)

    assert "raw runtime detail" not in str(raised.value)
    assert socket.closed


def test_successful_operation_signals_completion_and_cleans_owned_job(
    controller: KubernetesParserJobController, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = client.V1Job(metadata=client.V1ObjectMeta(uid="owned-uid"))
    create = Mock(return_value=created)
    wait_for_pod = Mock(return_value="owned-pod")
    exec_command = Mock(side_effect=[(b"0\n", 0), (b'{"valid":true}', 0), (b"", 0)])
    wait_terminal = Mock()
    cleanup = Mock()
    monkeypatch.setattr(controller, "_create_job", create)
    monkeypatch.setattr(controller, "_wait_for_pod", wait_for_pod)
    monkeypatch.setattr(controller, "_exec", exec_command)
    monkeypatch.setattr(controller, "_wait_for_terminal", wait_terminal)
    monkeypatch.setattr(controller, "_cleanup", cleanup)

    result = controller.execute(ParserOperation.EMBEDDED_TEXT, b"synthetic-pdf")

    assert result == b'{"valid":true}'
    assert exec_command.call_args_list[0].args[1][-1] == "oom-count"
    assert exec_command.call_args_list[1].args[1] == cast(Any, controller)._parser_command(
        ParserOperation.EMBEDDED_TEXT
    )
    assert "complete" in exec_command.call_args_list[2].args[1]
    assert wait_terminal.call_args.args[0].uid == "owned-uid"
    assert wait_terminal.call_args.args[1] == "Complete"
    assert cleanup.call_args.args[0].uid == "owned-uid"


def test_rejects_parser_job_when_local_concurrency_limit_is_reached(
    controller: KubernetesParserJobController, monkeypatch: pytest.MonkeyPatch
) -> None:
    limited = KubernetesParserJobController(
        connection=cast(Any, controller)._connection,
        settings=replace(
            cast(Any, controller)._settings,
            max_concurrent_jobs=1,
            startup_timeout_seconds=0.05,
        ),
    )
    create_started = Event()
    allow_create_to_finish = Event()

    def create_job(_name: str) -> client.V1Job:
        create_started.set()
        if not allow_create_to_finish.wait(timeout=2):
            raise TimeoutError("test did not release the first parser Job")
        return client.V1Job(metadata=client.V1ObjectMeta(uid="owned-uid"))

    create = Mock(side_effect=create_job)
    monkeypatch.setattr(limited, "_create_job", create)
    monkeypatch.setattr(limited, "_wait_for_pod", Mock(return_value="owned-pod"))
    monkeypatch.setattr(
        limited,
        "_exec",
        Mock(side_effect=[(b"0\n", 0), (b'{"valid":true}', 0), (b"", 0)]),
    )
    monkeypatch.setattr(limited, "_wait_for_terminal", Mock())
    monkeypatch.setattr(limited, "_cleanup", Mock())

    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(limited.execute, ParserOperation.EMBEDDED_TEXT, b"first-pdf")
        try:
            assert create_started.wait(timeout=1)
            with pytest.raises(ParserRuntimeUnavailable, match="concurrency limit"):
                limited.execute(ParserOperation.OCR, b"second-pdf")
        finally:
            allow_create_to_finish.set()

        assert first.result(timeout=2) == b'{"valid":true}'

    create.assert_called_once()


def test_nonzero_parser_exit_marks_job_failed_then_cleans(
    controller: KubernetesParserJobController, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        controller,
        "_create_job",
        Mock(return_value=client.V1Job(metadata=client.V1ObjectMeta(uid="owned-uid"))),
    )
    monkeypatch.setattr(controller, "_wait_for_pod", Mock(return_value="owned-pod"))
    execute = Mock(side_effect=[(b"0\n", 0), (b"", 7), (b"", 0)])
    terminal = Mock()
    cleanup = Mock()
    monkeypatch.setattr(controller, "_exec", execute)
    monkeypatch.setattr(controller, "_memory_limit_failure", Mock(return_value=None))
    monkeypatch.setattr(controller, "_wait_for_terminal", terminal)
    monkeypatch.setattr(controller, "_cleanup", cleanup)

    with pytest.raises(ParserExecutionFailed, match="returned a failure status"):
        controller.execute(ParserOperation.OCR, b"synthetic-pdf")

    assert "complete" in execute.call_args_list[2].args[1]
    assert execute.call_args_list[2].kwargs["stdin"] is None
    assert terminal.call_args.args[1] == "Failed"
    assert cleanup.call_args.args[0].uid == "owned-uid"


def test_cgroup_oom_signal_maps_a_failed_parser_job_to_memory_limit(
    controller: KubernetesParserJobController, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        controller,
        "_create_job",
        Mock(return_value=client.V1Job(metadata=client.V1ObjectMeta(uid="owned-uid"))),
    )
    monkeypatch.setattr(controller, "_wait_for_pod", Mock(return_value="owned-pod"))
    execute = Mock(side_effect=[(b"0\n", 0), (b"", 7), (b"1\n", 0)])
    terminal = Mock()
    cleanup = Mock()
    monkeypatch.setattr(controller, "_exec", execute)
    monkeypatch.setattr(controller, "_pod_container_oom_killed", Mock(return_value=False))
    monkeypatch.setattr(controller, "_wait_for_terminal", terminal)
    monkeypatch.setattr(controller, "_cleanup", cleanup)

    with pytest.raises(ParserProcessMemoryLimitExceeded, match="process exceeded its memory limit"):
        controller.execute(ParserOperation.OCR, b"synthetic-pdf")

    assert execute.call_args_list[0].args[1][-1] == "oom-count"
    assert execute.call_args_list[2].args[1][-1] == "oom-count"
    terminal.assert_not_called()
    assert cleanup.call_args.args[0].uid == "owned-uid"


def test_container_oom_status_maps_an_interrupted_exec_to_memory_limit(
    controller: KubernetesParserJobController, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        controller,
        "_create_job",
        Mock(return_value=client.V1Job(metadata=client.V1ObjectMeta(uid="owned-uid"))),
    )
    monkeypatch.setattr(controller, "_wait_for_pod", Mock(return_value="owned-pod"))
    execute = Mock(
        side_effect=[
            (b"0\n", 0),
            ApiException(status=0, reason="container terminated"),
            WebSocketConnectionClosedException("container is no longer running"),
        ]
    )
    cleanup = Mock()
    monkeypatch.setattr(controller, "_exec", execute)
    monkeypatch.setattr(controller, "_pod_container_oom_killed", Mock(return_value=True))
    monkeypatch.setattr(controller, "_cleanup", cleanup)

    with pytest.raises(
        ParserContainerMemoryLimitExceeded,
        match="container exceeded its memory limit",
    ):
        controller.execute(ParserOperation.OCR, b"synthetic-pdf")

    assert cleanup.call_args.args[0].uid == "owned-uid"


def test_pod_oom_kill_reason_maps_to_memory_limit_before_supervisor_ready(
    controller: KubernetesParserJobController, monkeypatch: pytest.MonkeyPatch
) -> None:
    pod = client.V1Pod(
        metadata=client.V1ObjectMeta(
            name="oom-pod",
            owner_references=[
                client.V1OwnerReference(
                    api_version="batch/v1",
                    kind="Job",
                    name="owned-job",
                    uid="owned-uid",
                    controller=True,
                )
            ],
        ),
        status=client.V1PodStatus(
            phase="Failed",
            container_statuses=[
                client.V1ContainerStatus(
                    name="parser",
                    image="parser:dev",
                    image_id="parser@sha256:synthetic",
                    ready=False,
                    restart_count=0,
                    state=client.V1ContainerState(
                        terminated=client.V1ContainerStateTerminated(
                            exit_code=137,
                            reason="OOMKilled",
                        )
                    ),
                )
            ],
        ),
    )
    core = Mock()
    core.list_namespaced_pod.return_value = client.V1PodList(items=[pod])
    connection = cast(Any, controller)._connection
    monkeypatch.setattr(connection, "new_api_client", lambda: nullcontext(object()))

    def fake_core_api(_api: object) -> Mock:
        return core

    monkeypatch.setattr(controller_module.client, "CoreV1Api", fake_core_api)

    with pytest.raises(
        ParserContainerMemoryLimitExceeded,
        match="container exceeded its memory limit",
    ):
        cast(Any, controller)._wait_for_pod(controller_module.OwnedParserJob("job", "owned-uid"))


def test_api_websocket_loss_maps_to_temporary_unavailability_and_cleans(
    controller: KubernetesParserJobController, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        controller,
        "_create_job",
        Mock(return_value=client.V1Job(metadata=client.V1ObjectMeta(uid="owned-uid"))),
    )
    monkeypatch.setattr(controller, "_wait_for_pod", Mock(return_value="owned-pod"))
    monkeypatch.setattr(
        controller,
        "_exec",
        Mock(
            side_effect=[
                (b"0\n", 0),
                WebSocketConnectionClosedException("private socket detail"),
            ]
        ),
    )
    monkeypatch.setattr(controller, "_memory_limit_failure", Mock(return_value=None))
    cleanup = Mock()
    monkeypatch.setattr(controller, "_cleanup", cleanup)

    with pytest.raises(
        ParserRuntimeUnavailable,
        match="connection is temporarily unavailable",
    ) as raised:
        controller.execute(ParserOperation.OCR, b"synthetic-pdf")

    assert "private socket detail" not in str(raised.value)
    assert cleanup.call_args.args[0].uid == "owned-uid"


def test_resource_quota_rejection_maps_to_temporary_unavailability() -> None:
    error = ApiException(
        status=403,
        reason="Forbidden",
        body=(
            '{"reason":"Forbidden","message":"exceeded quota: parser-job-budget, '
            'requested: requests.memory=512Mi, used: requests.memory=1Gi"}'
        ),
    )

    mapped = cast(Any, KubernetesParserJobController)._api_error(error)

    assert isinstance(mapped, ParserRuntimeUnavailable)
    assert str(mapped) == "Parser namespace resource quota is exhausted"


def test_non_quota_forbidden_error_remains_a_runtime_rejection() -> None:
    error = ApiException(
        status=403,
        reason="Forbidden",
        body='{"reason":"Forbidden","message":"User cannot create jobs"}',
    )

    mapped = cast(Any, KubernetesParserJobController)._api_error(error)

    assert isinstance(mapped, ParserRuntimeRejected)
    assert str(mapped) == "Kubernetes API refused the parser request (HTTP 403)"


def test_cleanup_uses_foreground_uid_precondition_and_confirms_absence(
    controller: KubernetesParserJobController, monkeypatch: pytest.MonkeyPatch
) -> None:
    batch = Mock()
    core = Mock()
    batch.read_namespaced_job.side_effect = ApiException(status=404)
    core.list_namespaced_pod.return_value = client.V1PodList(items=[])
    connection = cast(Any, controller)._connection
    monkeypatch.setattr(connection, "new_api_client", lambda: nullcontext(object()))

    def batch_api(api: Any) -> Mock:
        return batch

    def core_api(api: Any) -> Mock:
        return core

    def no_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(controller_module.client, "BatchV1Api", batch_api)
    monkeypatch.setattr(controller_module.client, "CoreV1Api", core_api)
    monkeypatch.setattr(controller_module.time, "sleep", no_sleep)

    cast(Any, controller)._cleanup(controller_module.OwnedParserJob("synthetic", "owned-uid"))

    delete_options = batch.delete_namespaced_job.call_args.kwargs["body"]
    assert delete_options.propagation_policy == "Foreground"
    assert delete_options.preconditions.uid == "owned-uid"
    assert core.list_namespaced_pod.call_count == 1


def test_cleanup_maps_api_connection_loss_to_bounded_runtime_unavailable(
    controller: KubernetesParserJobController, monkeypatch: pytest.MonkeyPatch
) -> None:
    batch = Mock()
    batch.delete_namespaced_job.side_effect = ConnectionError("private endpoint detail")
    connection = cast(Any, controller)._connection
    monkeypatch.setattr(connection, "new_api_client", lambda: nullcontext(object()))

    def fake_batch_api(_api: object) -> Mock:
        return batch

    monkeypatch.setattr(controller_module.client, "BatchV1Api", fake_batch_api)

    with pytest.raises(
        ParserRuntimeUnavailable,
        match="Kubernetes API connection is temporarily unavailable",
    ) as raised:
        cast(Any, controller)._cleanup(controller_module.OwnedParserJob("synthetic", "owned-uid"))

    assert "private endpoint detail" not in str(raised.value)
