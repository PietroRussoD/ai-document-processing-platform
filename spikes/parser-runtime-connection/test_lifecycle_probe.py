"""Fault checks for the standalone lifecycle controller; all data is synthetic."""

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import lifecycle_probe
import pytest
from connection_probe import ProbeError
from kubernetes import client
from kubernetes.client.exceptions import ApiException
from lifecycle_probe import LifecycleProbe, OwnedJob, job_manifest


@pytest.fixture
def boundary(monkeypatch: pytest.MonkeyPatch):
    batch = Mock()
    core = Mock()
    monkeypatch.setattr(lifecycle_probe, "build_configuration", lambda settings: None)
    monkeypatch.setattr(client, "ApiClient", lambda configuration: nullcontext(None))
    monkeypatch.setattr(client, "BatchV1Api", lambda api: batch)
    monkeypatch.setattr(client, "CoreV1Api", lambda api: core)
    monkeypatch.setattr(lifecycle_probe.time, "sleep", lambda seconds: None)
    return LifecycleProbe(SimpleNamespace(namespace="pdf-parser-probe")), batch, core


def test_cleanup_uses_uid_foreground_and_waits_for_pods(boundary) -> None:
    probe, batch, core = boundary
    job = OwnedJob("synthetic", "owned-uid")
    batch.read_namespaced_job.side_effect = ApiException(status=404)
    pod = client.V1Pod(
        metadata=client.V1ObjectMeta(
            owner_references=[
                client.V1OwnerReference(
                    api_version="batch/v1", kind="Job", name=job.name, uid=job.uid, controller=True
                )
            ]
        )
    )
    core.list_namespaced_pod.side_effect = [
        client.V1PodList(items=[pod]),
        client.V1PodList(items=[]),
    ]
    probe.cleanup(job)
    options = batch.delete_namespaced_job.call_args.kwargs["body"]
    assert options.propagation_policy == "Foreground"
    assert options.preconditions.uid == job.uid
    assert core.list_namespaced_pod.call_count == 2
    assert core.list_namespaced_pod.call_args.kwargs["label_selector"] == (
        "batch.kubernetes.io/controller-uid=owned-uid"
    )
    core.delete_namespaced_pod.assert_not_called()


def test_cleanup_is_idempotent_after_ttl_removal(boundary) -> None:
    probe, batch, core = boundary
    batch.delete_namespaced_job.side_effect = ApiException(status=404)
    batch.read_namespaced_job.side_effect = ApiException(status=404)
    core.list_namespaced_pod.return_value = client.V1PodList(items=[])
    probe.cleanup(OwnedJob("synthetic", "owned-uid"))


@pytest.mark.parametrize("status", [401, 403, 409, 500])
def test_cleanup_does_not_hide_delete_failures(boundary, status: int) -> None:
    probe, batch, _ = boundary
    batch.delete_namespaced_job.side_effect = ApiException(status=status, reason="synthetic-secret")
    with pytest.raises(ProbeError, match="deletion was refused") as error:
        probe.cleanup(OwnedJob("synthetic", "owned-uid"))
    assert "synthetic-secret" not in str(error.value)


def test_cleanup_refuses_replacement_and_timeout(boundary) -> None:
    probe, batch, _ = boundary
    batch.read_namespaced_job.return_value = SimpleNamespace(
        metadata=SimpleNamespace(uid="replacement-uid")
    )
    with pytest.raises(ProbeError, match="different UID"):
        probe.cleanup(OwnedJob("synthetic", "owned-uid"))
    with pytest.raises(ProbeError, match="cleanup deadline"):
        probe.cleanup(OwnedJob("synthetic", "owned-uid"), timeout=0)


@pytest.mark.parametrize("failure", [KeyboardInterrupt, RuntimeError])
@pytest.mark.parametrize("stage", ["wait_for_pod", "execute", "wait_for_terminal"])
def test_cleanup_runs_after_interruption_at_each_stage(
    boundary, monkeypatch: pytest.MonkeyPatch, failure, stage: str
) -> None:
    probe, batch, _ = boundary
    batch.create_namespaced_job.return_value = SimpleNamespace(
        metadata=SimpleNamespace(uid="owned-uid")
    )
    monkeypatch.setattr(probe, "wait_for_pod", Mock(return_value="synthetic-pod"))
    monkeypatch.setattr(probe, "execute", Mock(return_value=0))
    monkeypatch.setattr(probe, "wait_for_terminal", Mock())
    getattr(probe, stage).side_effect = failure
    cleanup = Mock()
    monkeypatch.setattr(probe, "cleanup", cleanup)
    with pytest.raises(failure):
        probe.run("success", "synthetic-image")
    assert cleanup.call_args.args[0].uid == "owned-uid"


def test_parser_error_finishes_failed_job_then_cleans(boundary, monkeypatch) -> None:
    probe, batch, _ = boundary
    batch.create_namespaced_job.return_value = SimpleNamespace(
        metadata=SimpleNamespace(uid="owned-uid")
    )
    monkeypatch.setattr(probe, "wait_for_pod", Mock(return_value="synthetic-pod"))
    execute = Mock(side_effect=[7, 0])
    terminal = Mock()
    cleanup = Mock()
    monkeypatch.setattr(probe, "execute", execute)
    monkeypatch.setattr(probe, "wait_for_terminal", terminal)
    monkeypatch.setattr(probe, "cleanup", cleanup)
    probe.run("error", "synthetic-image")
    assert "failure" in execute.call_args.args[1]
    assert terminal.call_args.args[1] == "Failed"
    cleanup.assert_called_once()


def test_unacknowledged_create_is_reconciled_before_cleanup(boundary, monkeypatch) -> None:
    probe, batch, _ = boundary
    batch.create_namespaced_job.side_effect = KeyboardInterrupt
    recover = Mock(return_value=OwnedJob("synthetic", "owned-uid"))
    cleanup = Mock()
    monkeypatch.setattr(probe, "recover_job", recover)
    monkeypatch.setattr(probe, "cleanup", cleanup)
    with pytest.raises(KeyboardInterrupt):
        probe.run("success", "synthetic-image")
    recover.assert_called_once()
    cleanup.assert_called_once_with(recover.return_value)


def test_recovery_refuses_unrelated_jobs(boundary) -> None:
    probe, batch, _ = boundary
    batch.read_namespaced_job.return_value = SimpleNamespace(
        metadata=SimpleNamespace(uid="unrelated-uid", labels={})
    )
    with pytest.raises(ProbeError, match="different owner"):
        probe.recover_job("synthetic")


def test_recovery_accepts_only_the_matching_run_label(boundary) -> None:
    probe, batch, _ = boundary
    batch.read_namespaced_job.return_value = client.V1Job(
        metadata=client.V1ObjectMeta(uid="owned-uid", labels={"parser-probe/run": "synthetic"})
    )
    assert probe.recover_job("synthetic") == OwnedJob("synthetic", "owned-uid")
    batch.read_namespaced_job.side_effect = ApiException(status=404)
    assert probe.recover_job("synthetic") is None
    batch.read_namespaced_job.side_effect = ApiException(status=403)
    with pytest.raises(ProbeError, match="could not be reconciled"):
        probe.recover_job("synthetic")


def test_cleanup_failure_does_not_claim_success(boundary, monkeypatch, capsys) -> None:
    probe, batch, _ = boundary
    batch.create_namespaced_job.return_value = SimpleNamespace(
        metadata=SimpleNamespace(uid="owned-uid")
    )
    monkeypatch.setattr(probe, "wait_for_pod", Mock(side_effect=KeyboardInterrupt))
    monkeypatch.setattr(probe, "cleanup", Mock(side_effect=ProbeError("Cleanup failed")))
    with pytest.raises(ProbeError, match="Cleanup failed"):
        probe.run("cancel", "synthetic-image")
    assert "cleaned" not in capsys.readouterr().out


@pytest.mark.parametrize("failure", [KeyboardInterrupt, ProbeError])
def test_exec_closes_socket_on_interruption(boundary, monkeypatch, failure) -> None:
    probe, _, _ = boundary
    socket = Mock()
    socket.update.side_effect = failure
    monkeypatch.setattr(lifecycle_probe.streaming, "stream", lambda *args, **kwargs: socket)
    with pytest.raises(failure):
        probe.execute("synthetic-pod", "synthetic-command")
    socket.close.assert_called_once()


def test_probe_has_bounded_fallback_and_restricted_pod() -> None:
    spec = job_manifest("synthetic", "synthetic-image")["spec"]
    assert spec["activeDeadlineSeconds"] == 60
    assert spec["ttlSecondsAfterFinished"] == 5
    assert spec["backoffLimit"] == 0
    pod = spec["template"]["spec"]
    assert pod["automountServiceAccountToken"] is False
    assert pod["restartPolicy"] == "Never"
    assert pod["securityContext"]["runAsUser"] == 10001
    container = pod["containers"][0]
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert container["securityContext"]["allowPrivilegeEscalation"] is False
