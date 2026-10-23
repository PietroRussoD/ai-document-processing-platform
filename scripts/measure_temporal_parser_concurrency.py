"""Submit two concurrent uploads and watch isolated OCR Pod concurrency."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from uuid import uuid4

import httpx
from kubernetes import client, config, watch
from kubernetes.client.exceptions import ApiException

DEFAULT_NAMESPACE = "pdf-parser-probe"
PARSER_RUN_LABEL = "parser.platform/run"
OCR_JOB_PREFIX = "pdf-parser-ocr-"
TERMINAL_RUN_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}
TERMINAL_DOCUMENT_STATUSES = {"REVIEW_REQUIRED", "APPROVED", "REJECTED", "UNSUPPORTED", "FAILED"}


def emit(**event: object) -> None:
    print(json.dumps(event, sort_keys=True), flush=True)


class OcrPodObserver:
    """Watch OCR Pods and sample each running container's cgroup memory peak."""

    def __init__(self, *, kubeconfig: Path, context: str, namespace: str) -> None:
        self.kubeconfig = kubeconfig
        self.context = context
        self.namespace = namespace
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.lock = threading.Lock()
        self.active: set[str] = set()
        self.pod_stops: dict[str, threading.Event] = {}
        self.pod_threads: dict[str, threading.Thread] = {}
        self.peaks: dict[str, int] = {}
        self.samples: dict[str, int] = {}
        self.seen: set[str] = set()
        self.max_active = 0
        self.overlap_seconds = 0.0
        self.overlap_started: float | None = None
        self.thread = threading.Thread(target=self._run, name="ocr-pod-watch", daemon=True)

    def start(self) -> None:
        self.thread.start()
        if not self.ready.wait(timeout=15):
            raise RuntimeError("Kubernetes Pod watch did not connect within 15 seconds")

    def close(self) -> None:
        self.stop.set()
        with self.lock:
            for signal in self.pod_stops.values():
                signal.set()
        self.thread.join(timeout=10)
        for thread in self.pod_threads.values():
            thread.join(timeout=5)

    def report(self) -> dict[str, object]:
        with self.lock:
            overlap = self.overlap_seconds
            if self.overlap_started is not None:
                overlap += time.monotonic() - self.overlap_started
            peaks = sorted(self.peaks.values())
            return {
                "event": "ocr_pod_resource_sample",
                "namespace": self.namespace,
                "label_selector": PARSER_RUN_LABEL,
                "ocr_pods_seen": len(self.seen),
                "max_simultaneous_ocr_pods": self.max_active,
                "sampled_overlap_seconds": round(overlap, 2),
                "pod_names": sorted(self.seen),
                "memory_peak_bytes": peaks,
                "memory_peak_mib": [round(value / 1_048_576, 1) for value in peaks],
                "memory_sample_count": dict(self.samples),
                "memory_peaks_include_kubectl_cat_sampler": True,
            }

    def _run(self) -> None:
        config.load_kube_config(config_file=str(self.kubeconfig), context=self.context)
        core = client.CoreV1Api()
        core.list_namespaced_pod(
            namespace=self.namespace,
            label_selector=PARSER_RUN_LABEL,
            limit=1,
            _request_timeout=10,
        )
        self.ready.set()
        resource_version: str | None = None
        while not self.stop.is_set():
            stream = watch.Watch()
            try:
                for event in stream.stream(
                    core.list_namespaced_pod,
                    namespace=self.namespace,
                    label_selector=PARSER_RUN_LABEL,
                    resource_version=resource_version,
                    timeout_seconds=30,
                    _request_timeout=35,
                ):
                    pod = event["object"]
                    metadata = pod.metadata
                    if metadata is None:
                        continue
                    resource_version = metadata.resource_version or resource_version
                    name = metadata.name or ""
                    labels = metadata.labels or {}
                    # The label carries the owning Job name. Restrict samples to
                    # OCR Jobs while still discovering Pods by the controller label.
                    if not labels.get(PARSER_RUN_LABEL, "").startswith(OCR_JOB_PREFIX):
                        continue
                    status = pod.status
                    running = (
                        event["type"] != "DELETED"
                        and status is not None
                        and status.phase == "Running"
                        and any(
                            item.state is not None and item.state.running is not None
                            for item in status.container_statuses or []
                        )
                    )
                    self._update(name, running)
                    if running:
                        self._start_sampler(name)
            except ApiException as error:
                emit(event="ocr_pod_watch_error", status=error.status, reason=error.reason)
                self.ready.set()
                if error.status in {401, 403}:
                    return
                time.sleep(1)
            except Exception as error:  # reconnect after a dropped watch stream
                emit(event="ocr_pod_watch_reconnecting", error=type(error).__name__)
                self.ready.set()
                time.sleep(1)
            finally:
                stream.stop()

    def _update(self, name: str, running: bool) -> None:
        now = time.monotonic()
        with self.lock:
            was_running = name in self.active
            if running:
                self.active.add(name)
                self.seen.add(name)
                self.max_active = max(self.max_active, len(self.active))
                if not was_running:
                    emit(event="ocr_pod_running", pod=name, active_ocr_pods=len(self.active))
            else:
                self.active.discard(name)
                signal = self.pod_stops.get(name)
                if signal is not None:
                    signal.set()
            if len(self.active) >= 2 and self.overlap_started is None:
                self.overlap_started = now
            elif len(self.active) < 2 and self.overlap_started is not None:
                self.overlap_seconds += now - self.overlap_started
                self.overlap_started = None

    def _start_sampler(self, name: str) -> None:
        with self.lock:
            if name in self.pod_threads:
                return
            signal = threading.Event()
            self.pod_stops[name] = signal
            thread = threading.Thread(
                target=self._sample_pod,
                args=(name, signal),
                name=f"memory-sample-{name[-8:]}",
                daemon=True,
            )
            self.pod_threads[name] = thread
            thread.start()

    def _sample_pod(self, name: str, stop: threading.Event) -> None:
        while not self.stop.is_set() and not stop.is_set():
            result = subprocess.run(
                [
                    "kubectl",
                    "--kubeconfig",
                    str(self.kubeconfig),
                    "--context",
                    self.context,
                    "--namespace",
                    self.namespace,
                    "exec",
                    name,
                    "--",
                    "cat",
                    "/sys/fs/cgroup/memory.peak",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                try:
                    peak = int(result.stdout.strip())
                except ValueError:
                    peak = None
                if peak is not None:
                    with self.lock:
                        self.peaks[name] = max(peak, self.peaks.get(name, 0))
                        self.samples[name] = self.samples.get(name, 0) + 1
            stop.wait(0.35)


def upload_document(api_url: str, token: str, pdf: bytes, index: int) -> str:
    with httpx.Client(base_url=api_url, timeout=180.0) as client_http:
        response = client_http.post(
            "/api/v1/documents",
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": f"parser-concurrency-{uuid4()}",
            },
            files={"document": (f"concurrent-parser-{index}.pdf", pdf, "application/pdf")},
        )
        response.raise_for_status()
        if response.status_code != 202:
            raise RuntimeError(f"Upload {index} returned HTTP {response.status_code}, expected 202")
        return str(response.json()["document_id"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="image-only synthetic PDF to upload twice")
    parser.add_argument("--api-url", default="http://127.0.0.1:18080")
    parser.add_argument("--token-env", default="DOCUMENT_PLATFORM_REVIEW_OPERATOR_TOKEN")
    parser.add_argument("--kubeconfig", type=Path, required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    parser.add_argument("--timeout-seconds", type=float, default=600)
    args = parser.parse_args()

    token = os.environ.get(args.token_env)
    if not token:
        parser.error(f"environment variable {args.token_env} is not set")
    if not args.pdf.is_file():
        parser.error(f"PDF does not exist: {args.pdf}")
    pdf = args.pdf.read_bytes()
    observer = OcrPodObserver(
        kubeconfig=args.kubeconfig,
        context=args.context,
        namespace=args.namespace,
    )
    try:
        observer.start()
        with httpx.Client(base_url=args.api_url, timeout=10.0) as health:
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                try:
                    if health.get("/health/ready").is_success:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(1)
            else:
                raise RuntimeError("API readiness timed out")

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            uploads = [
                pool.submit(upload_document, args.api_url, token, pdf, index) for index in (1, 2)
            ]
            document_ids = [future.result() for future in uploads]
        emit(event="uploads_accepted", count=2, fixture_bytes=len(pdf), http_status=202)

        statuses: dict[str, dict[str, object]] = {}
        deadline = time.monotonic() + args.timeout_seconds
        headers = {"Authorization": f"Bearer {token}"}
        with httpx.Client(base_url=args.api_url, timeout=10.0, headers=headers) as client_http:
            while time.monotonic() < deadline:
                for document_id in document_ids:
                    current_document = statuses.get(document_id, {})
                    current = current_document.get("current_run")
                    current_run_status = (
                        current.get("status") if isinstance(current, dict) else None
                    )
                    if (
                        current_run_status in TERMINAL_RUN_STATUSES
                        or current_document.get("status") in TERMINAL_DOCUMENT_STATUSES
                    ):
                        continue
                    response = client_http.get(f"/api/v1/documents/{document_id}")
                    response.raise_for_status()
                    statuses[document_id] = response.json()
                if len(statuses) == 2 and all(
                    (
                        isinstance(item.get("current_run"), dict)
                        and item["current_run"].get("status") in TERMINAL_RUN_STATUSES
                    )
                    or item.get("status") in TERMINAL_DOCUMENT_STATUSES
                    for item in statuses.values()
                ):
                    break
                time.sleep(0.5)
            else:
                raise TimeoutError("Document processing runs did not reach a terminal state")

        for document_id in document_ids:
            item = statuses[document_id]
            run = item.get("current_run") or {}
            output = run.get("processing_output") or {}
            ocr = output.get("ocr_text") or {}
            emit(
                event="workflow_complete",
                document_id=document_id,
                document_status=item.get("status"),
                run_status=run.get("status"),
                ocr_page_count=ocr.get("page_count"),
                ocr_character_count=ocr.get("character_count"),
                ocr_extracted_at=ocr.get("extracted_at"),
                failure=run.get("failure"),
            )
        time.sleep(2)
        return 0
    finally:
        observer.close()
        emit(**observer.report())


if __name__ == "__main__":
    raise SystemExit(main())
