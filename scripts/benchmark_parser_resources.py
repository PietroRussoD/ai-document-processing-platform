"""Measure isolated parser resource use in disposable, network-disabled containers."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
MAX_INPUT_BYTES = 20 * 1024 * 1024
MAX_OUTPUT_BYTES = 1_000_100
_CONTAINER_PROBE = r"""
import asyncio, json, os, shutil, sys, threading, time

def read_value(path):
    try:
        return open(path, encoding="ascii").read().strip()
    except (OSError, UnicodeError):
        return None

def cpu_usage():
    raw = read_value("/sys/fs/cgroup/cpu.stat")
    if raw is None:
        return None
    for line in raw.splitlines():
        key, value = line.split()
        if key == "usage_usec":
            return int(value)
    return None

def oom_kills():
    raw = read_value("/sys/fs/cgroup/memory.events")
    if raw is None:
        return None
    for line in raw.splitlines():
        key, value = line.split()
        if key == "oom_kill":
            return int(value)
    return None

def tmp_used():
    try:
        usage = shutil.disk_usage("/tmp")
        return usage.total - usage.free
    except OSError:
        return None

pdf = sys.stdin.buffer.read(int(os.environ["PARSER_MAX_INPUT_BYTES"]) + 1)
cpu_before = cpu_usage()
oom_before = oom_kills()
try:
    memory_limit = int(read_value("/sys/fs/cgroup/memory.max"))
except (TypeError, ValueError):
    memory_limit = None
tmp_peak = 0
sampling = True

def sample_tmp():
    global tmp_peak
    while sampling:
        used = tmp_used()
        if used is not None:
            tmp_peak = max(tmp_peak, used)
        time.sleep(0.01)

sampler = threading.Thread(target=sample_tmp, daemon=True)
sampler.start()
started = time.perf_counter()
status = "completed"
parser_exit_code = None
page_count = None
character_count = None
try:
    from document_platform.parser_worker import process_pdf

    result = asyncio.run(
        process_pdf(
            os.environ["PARSER_OPERATION"],
            pdf,
            max_output_bytes=int(os.environ["PARSER_MAX_OUTPUT_BYTES"]),
        )
    )
    parser_exit_code = 0 if result is not None else 7
    if result is not None:
        envelope = json.loads(result)
        page_count = envelope.get("page_count")
        character_count = envelope.get("character_count")
    else:
        status = "parser_failed"
except TimeoutError:
    status = "parser_timeout"
finally:
    elapsed_seconds = time.perf_counter() - started
    sampling = False
    sampler.join(timeout=1)

cpu_after = cpu_usage()
oom_after = oom_kills()
try:
    memory_peak = int(read_value("/sys/fs/cgroup/memory.peak"))
except (TypeError, ValueError):
    memory_peak = None
cpu_delta = (
    cpu_after - cpu_before
    if cpu_before is not None and cpu_after is not None
    else None
)
oom_delta = (
    oom_after - oom_before
    if oom_before is not None and oom_after is not None
    else None
)
print(json.dumps({
    "status": status,
    "parser_exit_code": parser_exit_code,
    "elapsed_seconds": round(elapsed_seconds, 3),
    "memory_peak_bytes": memory_peak,
    "memory_limit_bytes": memory_limit,
    "cpu_usage_usec": cpu_delta,
    "tmp_peak_bytes_sampled": tmp_peak,
    "oom_kill_delta": oom_delta,
    "page_count": page_count,
    "character_count": character_count,
}), flush=True)
"""


def _run_one(
    *,
    pdf_path: Path,
    run_number: int,
    operation: str,
    image: str,
    memory: str,
    cpu: str,
    tmp_size: str,
    timeout: float,
) -> dict[str, object]:
    name = f"parser-benchmark-{uuid4().hex[:16]}"
    command = [
        "docker",
        "run",
        "--interactive",
        "--name",
        name,
        "--pull=never",
        "--network=none",
        f"--memory={memory}",
        f"--memory-swap={memory}",
        f"--cpus={cpu}",
        "--pids-limit=128",
        "--read-only",
        "--tmpfs",
        f"/tmp:rw,noexec,nosuid,nodev,size={tmp_size}",
        "--user=10001:10001",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--env",
        "PYTHONPATH=/benchmark/src",
        "--env",
        f"PARSER_OPERATION={operation}",
        "--env",
        f"PARSER_MAX_INPUT_BYTES={MAX_INPUT_BYTES}",
        "--env",
        f"PARSER_MAX_OUTPUT_BYTES={MAX_OUTPUT_BYTES}",
        "--env",
        f"PARSER_TIMEOUT_SECONDS={timeout}",
        "--volume",
        f"{ROOT / 'src'}:/benchmark/src:ro",
        "--entrypoint",
        "python",
        image,
        "-c",
        _CONTAINER_PROBE,
    ]
    started = time.perf_counter()
    result: subprocess.CompletedProcess[str] | None = None
    timed_out = False
    try:
        result = subprocess.run(
            command,
            input=pdf_path.read_bytes(),
            capture_output=True,
            timeout=timeout + 30,
            check=False,
        )
    except subprocess.TimeoutExpired:
        timed_out = True
    finally:
        inspected = subprocess.run(
            ["docker", "inspect", "--format", "{{json .State}}", name],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        subprocess.run(
            ["docker", "rm", "--force", name],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

    state: dict[str, object] = {}
    if inspected.returncode == 0:
        try:
            decoded = json.loads(inspected.stdout)
            if isinstance(decoded, dict):
                state = decoded
        except json.JSONDecodeError:
            pass
    metrics: dict[str, object] = {}
    if result is not None and result.returncode == 0:
        try:
            decoded = json.loads(result.stdout)
            if isinstance(decoded, dict):
                metrics = decoded
        except json.JSONDecodeError:
            pass
    return {
        "fixture": pdf_path.name,
        "run": run_number,
        "operation": operation,
        "image": image,
        "memory_limit": memory,
        "cpu_limit": cpu,
        "status": "container_timeout" if timed_out else metrics.get("status", "container_failed"),
        "elapsed_seconds": metrics.get("elapsed_seconds", round(time.perf_counter() - started, 3)),
        "memory_peak_bytes": metrics.get("memory_peak_bytes"),
        "memory_limit_bytes": metrics.get("memory_limit_bytes"),
        "cpu_usage_usec": metrics.get("cpu_usage_usec"),
        "tmp_peak_bytes_sampled": metrics.get("tmp_peak_bytes_sampled"),
        "oom_kill_delta": metrics.get("oom_kill_delta"),
        "container_oom_killed": state.get("OOMKilled"),
        "parser_exit_code": metrics.get("parser_exit_code"),
        "page_count": metrics.get("page_count"),
        "character_count": metrics.get("character_count"),
    }


def _repeat_single_page_fixture(source_path: Path, page_count: int, directory: Path) -> Path:
    import pymupdf

    target_path = directory / f"repeated-{page_count}-pages.pdf"
    with pymupdf.open(source_path) as source:
        if source.page_count != 1:
            raise ValueError("repeat-single-page requires a one-page source PDF")
        with pymupdf.open() as target:
            for _ in range(page_count):
                target.insert_pdf(source)
            target.save(target_path)
    return target_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", nargs="+", type=Path, help="synthetic PDF fixtures to measure")
    parser.add_argument("--image", default="document-platform-api:dev")
    parser.add_argument("--operation", choices=("embedded-text", "ocr"), default="ocr")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--memory", default="512m")
    parser.add_argument("--cpu", default="1")
    parser.add_argument("--tmp-size", default="64m")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument(
        "--repeat-single-page",
        type=int,
        default=0,
        metavar="PAGES",
        help="also benchmark a synthetic PDF made by repeating the single input page",
    )
    parser.add_argument(
        "--repeat-only",
        action="store_true",
        help="benchmark only the generated repeated-page PDF, not its one-page source",
    )
    args = parser.parse_args()

    if (
        args.runs < 1
        or args.concurrency < 1
        or args.concurrency > 4
        or args.timeout <= 0
        or args.repeat_single_page < 0
    ):
        parser.error("runs and timeout must be positive; concurrency must be between 1 and 4")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", args.image):
        parser.error("image must be a bounded local Docker image reference")
    paths = [path.resolve() for path in args.pdf]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        parser.error(f"PDF fixture does not exist: {missing[0]}")

    temporary_directory: tempfile.TemporaryDirectory[str] | None = None
    try:
        if args.repeat_single_page:
            if len(paths) != 1:
                parser.error("--repeat-single-page requires exactly one source PDF")
            temporary_directory = tempfile.TemporaryDirectory(prefix="parser-benchmark-")
            repeated = _repeat_single_page_fixture(
                paths[0],
                args.repeat_single_page,
                Path(temporary_directory.name),
            )
            paths = [repeated] if args.repeat_only else [*paths, repeated]
        elif args.repeat_only:
            parser.error("--repeat-only requires --repeat-single-page")
        jobs = [
            (path, run_number)
            for path in paths
            for run_number in range(1, args.runs + 1)
        ]
        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            futures = [
                executor.submit(
                    _run_one,
                    pdf_path=path,
                    run_number=run_number,
                    operation=args.operation,
                    image=args.image,
                    memory=args.memory,
                    cpu=args.cpu,
                    tmp_size=args.tmp_size,
                    timeout=args.timeout,
                )
                for path, run_number in jobs
            ]
            for future in as_completed(futures):
                print(json.dumps(future.result(), sort_keys=True), flush=True)
    except (OSError, subprocess.SubprocessError) as error:
        print(f"Benchmark infrastructure failed ({type(error).__name__})", file=sys.stderr)
        return 1
    except ValueError as error:
        parser.error(str(error))
    finally:
        if temporary_directory is not None:
            temporary_directory.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
