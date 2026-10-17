# PDF Parser Isolation Integration Proposal

Status: proposed architecture; no application integration is implemented.

This proposal refines the deferred parser-isolation work described in the
[isolation design](pdf-parser-isolation-design.md). The project is still on
`1.2.0.dev0`, and the v1.2.0 release remains in development. Do not implement
this proposal as part of v1.2.0 or change the project version while reviewing
it.

## Goal and scope

Move every operation that opens or rasterizes an uploaded PDF out of the API
and Temporal worker processes. Run each parsing operation in a short-lived,
restricted Kubernetes Job. Keep the API, database and Temporal workflow as the
trusted application boundary.

This is a local portfolio and learning exercise using synthetic documents. It
does not claim kernel-level isolation, public-service readiness or protection
against every vulnerability in the container runtime.

## Proposed vertical slice

Keep the existing two Temporal activities and their order:

1. `extract-document-text` starts one parser Job. The Job checks the PDF
   structure, encryption and page limit, then extracts embedded text.
2. `extract-ocr-text` starts a separate parser Job only when embedded text
   quality requires OCR. The Job rasterizes pages and runs Tesseract.

This moves the upload-time inspection into the first existing parsing stage.
It avoids adding a new Temporal stage or changing workflow history. The
application activities continue to persist extraction records and return only
small metadata to Temporal; extracted text must not become workflow input,
output or history.

The API accepts and stores a file after checking its declared media type,
non-empty body and byte limit. It no longer opens the PDF. Structural,
encrypted-file and page-limit errors therefore become asynchronous processing
failures after the API returns `202 Accepted`. The document status and failure
stage must make that outcome clear in the console.

## Data model change required by asynchronous inspection

The current upload path requires a page count before it registers a document.
The parser cannot provide that value until the worker starts the first Job.
Represent the count as unknown while the document is queued:

- Change `Document.page_count`, `RegisterDocument` and the status API field to
  allow `null` until embedded-text extraction succeeds.
- Migrate the database constraint to allow `NULL` or a positive page count;
  keep all existing counts unchanged and do not use zero as a placeholder.
- In the same transaction that stores the first extraction, persist its page
  count. Reject a later result if it disagrees with an already known count.
- Show an unavailable or pending value in the console while the count is
  unknown. Regenerate the TypeScript API client from OpenAPI.

Only a successfully parsed PDF receives a page count. A failed first parse
keeps the field unknown. Reprocessing an existing document retains its known
count and verifies that the parser reports the same value.

## Job and transfer boundary

The Compose worker remains the trusted controller. It reads the stored PDF
from the existing `LocalBlobStore`, creates a Job in a dedicated parser
namespace, then starts a fixed parser command inside the running Job through
the Kubernetes `pods/exec` subresource. It streams the file to that command's
stdin and receives a bounded structured result through that exec session's
stdout channel. This is the exec process's remote stream, not the Job
container's normal stdout or stderr, so the result is not written to container
logs. The worker validates the result and persists it through the existing
application handler.

The parser Job receives no application volume, database or Temporal
credentials, Kubernetes API token, operator token or external network route.
It gets only its private bounded scratch volume. Use a fixed argument vector;
never interpolate a filename, PDF value or other user input into a shell
command. Do not use the Docker socket, host paths, ConfigMaps or Secrets as PDF
transport, and do not use logs as the result channel.

The Job container runs a small supervisor as PID 1. After it has validated
and persisted the result, the controller invokes a fixed job-control command
with a `success` or `failure` value. The command writes a completion marker to
the private scratch volume; the supervisor exits with the corresponding
status, allowing the Job to complete and `ttlSecondsAfterFinished` to clean it
up. If the worker disappears, `activeDeadlineSeconds` terminates the Job and
TTL provides fallback cleanup. The worker also deletes the Job in a `finally`
path when it can. Both commands use fixed argument vectors and never execute a
shell.

The Kubernetes Python client requires its streaming helper for exec calls. The
official client also warns that streaming changes the API client's protocol
handling; recreate the API client before subsequent ordinary API calls. The
exact stdin/stdout behavior, exit status, cancellation and memory use must be
proven in a standalone spike before this transport is accepted. See the
[Kubernetes Pod exec API](https://kubernetes.io/docs/reference/kubernetes-api/core/pod-v1/)
and the [official Python client guidance](https://github.com/kubernetes-client/python).

## Parser Job restrictions

Every Job should use:

- a dedicated namespace with the Pod Security `restricted` standard;
- a non-root UID, read-only root filesystem, no privilege escalation, all
  capabilities dropped and the runtime-default seccomp profile;
- `automountServiceAccountToken: false`, no service account permissions,
  default-deny ingress and egress, and no service or published port;
- one bounded `emptyDir` for scratch files, with no `hostPath` or application
  volume;
- `restartPolicy: Never`, `backoffLimit: 0`, a measured active deadline and
  `ttlSecondsAfterFinished`;
- measured CPU, memory and ephemeral-storage requests and limits, plus a
  namespace quota and a cap on concurrent parser activities.

Kubernetes configures the per-Pod process limit at the kubelet level through
`podPidsLimit`; it is not a Pod resource limit. Configure and verify it on
every node in the dedicated Kind cluster, and check that the value does not
prevent cluster components from running. See [Kubernetes process ID
limits](https://kubernetes.io/docs/concepts/policy/pid-limiting/).

Use a dedicated, namespace-scoped controller identity for the worker. Its
permissions should be limited to creating, reading, watching and deleting Jobs
in that namespace; reading and watching Pods; and the verbs required on the
`pods/exec` subresource. The spike found that the tested client/server pair
needed both `get` and `create` on `pods/exec`; verify this against the versions
used by the application. Do not give the worker the default Kind administrator
kubeconfig or access to a remote production-named context. The parser container
itself must never receive this identity.

## Result contract

The parser returns one versioned JSON object for the requested operation. The
worker rejects results with an unsupported protocol version, malformed JSON,
unexpected fields, a page count outside the configured limit, text above the
existing character limit, inconsistent character counts, invalid UTF-8 or an
input digest that does not match the submitted PDF. Cap the encoded response
size as well as the character count.

The worker must not log the PDF, extracted text, OCR text, parser stdout or
credentials. Persist the result in PostgreSQL before returning a small summary
from the Temporal activity. Map invalid input, parser crash, timeout, resource
termination, oversized output and runtime unavailability to bounded failure
codes; never persist raw parser exceptions as user-visible errors.

Keep the existing upload-size, page-count, extracted-character, OCR-pixel and
per-page timeout limits. Measure Job CPU, memory, scratch space, startup time
and total deadlines against the synthetic fixtures before choosing numeric
Kubernetes limits. The existing aggregate Compose limits are not a substitute
for per-Job limits.

## Required integration spike before implementation

The first implementation step should be a disposable infrastructure spike,
not an application change. On a newly created, separately named Kind cluster
with Calico and an isolated kubeconfig, prove that a restricted Job can:

1. receive a synthetic PDF up to the configured upload limit over `pods/exec`
   stdin without buffering the entire transfer unexpectedly;
2. return a bounded result up to the configured extraction limit over the exec
   channel, with the correct process exit status and without placing content
   in Job logs or Temporal history;
3. be cancelled, time out and be deleted after both success and failure;
4. run under the proposed namespace-scoped controller permissions while the
   parser Pod has no token and cannot reach another Pod or the Internet.

Also prove that the Compose worker can reach only this separate local cluster
using the scoped credential. Do not use the existing `hub` cluster or the
remote context. If binary streaming, output bounds, scoped credentials or
cleanup cannot be demonstrated, stop and compare a narrowly scoped artifact
broker design. Do not weaken the network policy or mount the Docker socket to
make the integration appear to work.

### Initial spike results — 2026-10-17

The disposable Kind 1.37 cluster used Calico 3.33, a dedicated kubeconfig, a
`restricted` namespace and a default-deny ingress/egress policy. The probe Job
was accepted with a non-root UID, read-only root filesystem, dropped
capabilities, `RuntimeDefault` seccomp, bounded `emptyDir`, and automatic
service-account token mounting disabled. The cluster was deleted after the
probe; no application code or project version was changed.

| Check | Result | Evidence and limit |
| --- | --- | --- |
| Configured transfer and extraction sizes | Pass at transport level | The Python client 37.0.1 streamed a deterministic 20 MiB file through stdin in 64 KiB chunks; the restricted Pod reported the same byte count and SHA-256. It then returned a JSON envelope containing exactly 1,000,000 ASCII characters (1,000,018 bytes total), collected below a 1,000,100-byte cap, with exit code `0`. This exercises the configured byte and character counts, not the application parser, OCR, Unicode expansion, peak memory or CPU use. Keep a separate encoded-response byte cap because non-ASCII text and JSON escaping can produce a larger payload. |
| Parser resource profile | Measured, single runs | Ran the exact current parser source from `document-platform-api:dev` in disposable containers with network disabled, read-only root, capabilities dropped, no-new-privileges, 1 CPU, 512 MiB memory, 128 PIDs and a 64 MiB `/tmp` tmpfs. The image's three parser module hashes matched the working tree. The one-page digital fixture (1,370 bytes) used 0.044 s wall time and peaked at 41.0 MiB cgroup memory during inspection; embedded-text extraction returned 266 characters in 0.034 s and peaked at 40.6 MiB. Wall and CPU measurements start after Python imports; memory peaks include the interpreter and imported modules. |
| OCR resource profile | Measured, single runs | The one-page scanned fixture (129,112 bytes) returned 243 characters in 0.792 s, with 0.741 s cgroup CPU and a 140.0 MiB cgroup memory peak (39.1 MiB at start). A synthetic 860-byte page at 200 DPI rasterized to 4,472 × 4,472 pixels (19,998,784, below the 20-million-pixel cap) and completed in 1.015 s, with 1.026 s cgroup CPU and a 252.9 MiB memory peak (39.1 MiB at start). A `/tmp` usage sampler polling every 10 ms observed no scratch use; a shorter transient write could be missed. |
| Binary stdin | Pass | The Python client 37.0.1 streamed a deterministic 1 MiB payload. After explicitly closing the stdin channel, the parser's SHA-256 matched the sender. A fixed-size reader had previously stopped at its first 64 KiB read, so the parser must consume until EOF rather than assume a read fills the requested buffer. |
| Bounded stdout | Pass, at probe scale | The host collector stopped and closed the stream after 128 KiB while the probe command produced 4 MiB. This demonstrates a consumer-side cap, not the final extraction limit or peak memory use. |
| Process exit status | Pass | Exit code `7` arrived in the exec status channel. |
| Job logs | Pass | A marker returned through exec stdout was absent from the Job container logs. |
| Scoped RBAC | Partial | With a short-lived service-account token, the probe could read/list Pods and create Jobs but could not read Secrets. Exec failed when the role allowed only `get` on `pods/exec`; it worked after granting both `get` and `create` on that subresource. Confirm the required verbs against the exact Kubernetes and client versions used by the application. |
| Network policy | Pass for pod-to-pod ingress and egress | The earlier Calico probe recorded a client reaching a parser-labeled HTTP Pod before policy, then timing out after ingress was denied. A parser-labeled client reached a Pod in another namespace by IP before an egress-only deny policy, then timed out after the policy was applied. The default-deny DNS probe in this spike also timed out. Internet egress is not verified; see the following row. See the [isolation design spike](pdf-parser-isolation-design.md). |
| Internet egress | Not verifiable in this environment | A follow-up attempt could not establish a direct HTTPS baseline to `1.1.1.1:443`; the connection timed out. Calico installation also stalled while fetching images from `quay.io` and Docker Hub's layer CDN, so no comparison before and after a NetworkPolicy was possible. This is an environment limitation, not evidence that the policy blocks Internet access; repeat the probe in a network-enabled environment. |
| Disconnect and cancellation | Failure as cancellation | Closing the client WebSocket did not stop the remote child process; it continued and created a marker. A disconnected exec session is therefore not a cancellation mechanism. The controller must delete the Job or invoke an explicit fixed job-control command; `activeDeadlineSeconds` remains the fallback for abandoned Jobs. |
| Job completion and TTL | Pass for success and active deadline | The completion marker let a Job finish, and a short TTL removed the completed Job and Pod. The earlier isolation spike also observed a Job fail with `DeadlineExceeded`, followed by TTL removal of the Job and Pod. This verifies Kubernetes cleanup, not worker-driven cancellation or application error handling; see the [isolation design spike](pdf-parser-isolation-design.md). |
| PID limit | Pass | On a separate Kind 1.37 cluster, both nodes were Ready with `podPidsLimit: 128`. Reading the cgroup hierarchy from the worker showed `pids.max=128` on the Pod parent and `pids.max=9397` on the container cgroup, confirming that the effective Pod limit is 128 without a process-spawn stress test. |
| Compose-network reachability | Pass for network and credential smoke test | A disposable container using `document-platform-api:dev` on `ai-document-processing-platform_default`, with `host.docker.internal` mapped to the host gateway, reached the temporary Kind API with TLS verification enabled. The scoped token received `200` for listing Pods, `403` for listing Secrets, and SelfSubjectAccessReview allowed `get/create pods/exec` plus `create jobs` while denying `get secrets`. This did not exercise the `document_platform.worker` configuration or Kubernetes client integration. |
| Worker Kubernetes configuration | Not implemented | `worker.py` still constructs local PyMuPDF and Tesseract extractors. `Settings`, `compose.yaml` and `pyproject.toml` define no Kubernetes endpoint, CA, controller token or Kubernetes client dependency. This is expected before the proposed integration; the network smoke test did not run the worker process. |

The transport is promising enough to continue without designing an artifact
broker yet, but this spike does not clear the full integration gate. These
single-run measurements are baselines, not resource-limit recommendations;
they cover the existing one-page fixtures and one page near the raster-pixel
cap, not 20 MiB PDFs, 50-page documents, million-character parser output,
concurrent work or adversarial PDFs. Before implementation, define and
validate the worker's endpoint, CA and scoped-token configuration; verify
Internet egress denial and worker-driven cleanup after parser errors or
cancellation; and extend resource measurements across representative and
worst-case synthetic documents. Preserve the explicit stdin half-close and
bounded streaming behavior in the implementation.

## Acceptance criteria for a later implementation

- The API and worker no longer instantiate PyMuPDF or Tesseract directly.
- All PDF inspection, embedded-text extraction, rasterization and OCR happen
  in the restricted parser Jobs.
- The current Temporal stage sequence and small activity return contracts
  remain compatible with recorded histories.
- Upload still returns promptly with `202`; parser errors appear as bounded
  asynchronous failures, and the console handles an unknown page count.
- The parser receives one PDF at a time, has no application credentials or
  network access, and cannot read the Compose data volume.
- Results are size-checked, validated and persisted by the trusted worker;
  document text does not enter logs or Temporal history.
- Timeouts, crashes, oversized results, cancellation, retries and orphan
  cleanup have focused tests using synthetic fixtures.
- Resource limits are based on measurements and the documentation describes
  this as per-Job containment on `runc`, not as a kernel sandbox.

## References

- [Kubernetes Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Kubernetes security contexts](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/)
- [Kubernetes Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
- [Kubernetes Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Kubernetes process ID limits](https://kubernetes.io/docs/concepts/policy/pid-limiting/)
- [Kubernetes Python client](https://github.com/kubernetes-client/python)
