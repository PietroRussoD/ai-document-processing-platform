# Parser Job lifecycle probe

This standalone companion verifies controller-driven Job cleanup using the
existing [explicit connection contract](README.md) and scoped controller Role.
It does not change the application's worker, dependencies or version.
Commands execute synthetic Python code, not PyMuPDF or Tesseract.

## Lifecycle contract

The controller creates a uniquely named Job and retains its Kubernetes UID.
It waits for an owned Pod, then executes a fixed synthetic command through
`pods/exec`. For success and parser failure, it writes a completion marker
through another fixed command; the supervisor exits with status 0 or 1.
The controller observes the corresponding `Complete` or `Failed` Job condition.

A `finally` block deletes the Job with foreground propagation, a UID
precondition and a one-second termination grace period. Cleanup polls until
both the Job and its owned Pods have disappeared. It requires no direct Pod
deletion permission. A 404 is idempotent; an authorization failure, UID
conflict, observation error or expired cleanup polling budget is a failure.
The CLI emits `cleaned` only after confirming removal.

Cleanup creates a fresh REST ApiClient because exec streaming changes its
client's transport. If Job creation has no acknowledged result, recovery
looks up the unique name and checks its run label before attempting cleanup.
An unreachable API can prevent reconciliation and cleanup; the Job deadline
and TTL remain necessary. A Job may become visible after a recovery lookup
returns 404, so that lookup alone cannot guarantee immediate removal.

The synthetic Job has no mounted API token. It uses UID/GID 10001, a read-only
root filesystem, dropped capabilities, no privilege escalation, default
seccomp, CPU/memory limits and a bounded private memory-backed `emptyDir`.
`backoffLimit` is 0, `activeDeadlineSeconds` is 60 and
`ttlSecondsAfterFinished` is 5. These deliberately short values exercise
fallback behavior; they are not proposed production parser limits.

## Reproduce locally

Use the [host-side recipe](README.md) with a separate cluster named
`ai-doc-parser-lifecycle-probe` and its own bootstrap directory and kubeconfig.
Never use the current kubectl context or the existing `hub` cluster.
Load the already built application image into this temporary cluster:

```sh
kind load docker-image document-platform-api:dev --name ai-doc-parser-lifecycle-probe
```

After bootstrapping the CA, endpoint and short-lived scoped token, run from
the repository root. The controller receives no administrator kubeconfig:

```sh
"$probe_python" spikes/parser-runtime-connection/lifecycle_probe.py \
  --endpoint "$(cat "$probe_dir/endpoint")" --namespace pdf-parser-probe \
  --ca-file "$probe_dir/ca.pem" --token-file "$probe_dir/token" \
  --scenario success
```

Repeat with `--scenario error`. Both commands should exit 0 and emit
`executing`, followed by `cleaned`. For the error scenario this means the
probe successfully verified a synthetic parser exit status of 7 and a failed
Job, followed by cleanup.

For `--scenario cancel`, interrupt the CLI once with Ctrl+C while its synthetic
parser sleeps. It should emit `cleaned` and `cancelled`, then exit 130.
For `--scenario abandon`, terminate the CLI with SIGKILL from another terminal
while the parser sleeps. No Python `finally` block can run in that case.
Observe `DeadlineExceeded` and subsequent Job/Pod removal using the explicit
bootstrap kubeconfig. Do not manually delete the Job during this fallback
check. The live verification first confirmed that `/scratch/parser-started`
existed through a separate scoped exec before sending either signal; the
`executing` event alone is emitted before exec starts.

Run the focused offline checks in the separate SDK environment:

```sh
"$probe_python" -m pytest -o addopts= \
  spikes/parser-runtime-connection/test_connection_probe.py \
  spikes/parser-runtime-connection/test_lifecycle_probe.py -q
.venv/bin/ruff check spikes/parser-runtime-connection
.venv/bin/ruff format --check spikes/parser-runtime-connection
.venv/bin/pyright --project spikes/parser-runtime-connection --pythonpath "$probe_python"
```

Remove this temporary cluster and bootstrap directory after verification.

## Recorded validation — 2026-10-18

The live check used a dedicated Kind Kubernetes 1.37 cluster, Python SDK
37.0.1 and the cached `document-platform-api:dev` image. All controller
operations used the scoped service-account token with verified TLS. The
administrator kubeconfig was used only for bootstrap and independent final
metadata inspection. This cluster used Kind's default CNI; this run makes no
new network-isolation claim.

| Scenario | Observed result |
| --- | --- |
| Success | Exec exited 0, supervisor completed the Job, and foreground cleanup removed Job and Pod. Total 3.78 s in one run. |
| Parser failure | Exec exited 7, supervisor failed the Job, and foreground cleanup removed Job and Pod. Total 3.78 s in one run. |
| Controller SIGINT | A running synthetic parser was interrupted through controller cancellation; cleanup removed Job and Pod in 3.69 s after the signal. CLI exited 130. Repeating cleanup succeeded. |
| Controller SIGKILL | No controller cleanup ran. Kubernetes reported terminal `Failed` with reason `DeadlineExceeded`, then TTL removed Job and Pod. Removal was observed 66.54 s after the signal. |
| Final resources | Scoped API lists and independent bootstrap inspection found zero Jobs and zero Pods in the dedicated namespace. |

Offline checks passed 53 tests across the connection and lifecycle modules,
including 21 lifecycle cases. They cover interruption during startup, exec
and terminal-state observation; UID preconditions; duplicate cleanup; failure
reporting; creation recovery; and WebSocket closure on interruption.
Ruff and the spike's strict Pyright check also passed.

The cluster and temporary credentials were removed after validation. This
demonstrates the synchronous standalone controller contract. It does not
verify Temporal Activity cancellation, heartbeat handling, async cancellation
shielding, repeated signals during cleanup, unavailable API recovery, actual
PDF/OCR processes or cleanup while transferring a maximum-size payload.
