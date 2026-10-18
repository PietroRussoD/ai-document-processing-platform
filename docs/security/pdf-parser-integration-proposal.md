# PDF Parser Isolation Integration Proposal

Status: local runtime topology selected and network-tested; no application
integration is implemented.

This proposal refines the parser-isolation work described in the
[isolation design](pdf-parser-isolation-design.md). The local single-operator
v1.2.0 release is closed. The separate [v1.3.0 scope](../releases/v1.3.0.md)
proposes integrating the selected local runtime for the portfolio exercise;
application integration gates remain open.

## Goal and scope

Move every operation that opens or rasterizes an uploaded PDF out of the API
and Temporal worker processes. Run each parsing operation in a short-lived,
restricted Kubernetes Job. Keep the API, database and Temporal workflow as the
trusted application boundary.

This is a local portfolio and learning exercise using synthetic documents. It
does not claim kernel-level isolation, public-service readiness or protection
against every vulnerability in the container runtime.

## Selected local topology

Keep the application API, PostgreSQL, dispatcher, Temporal and worker in
Compose. Run each parser operation in a short-lived Job on a separately named
Kind cluster with Calico. The worker remains the only controller. It connects
to the Kind API through `host.docker.internal:<published-port>`; the API server
binds host loopback and its certificate includes `host.docker.internal`.
Configure the worker with an explicit endpoint, CA file and short-lived,
namespace-scoped token. Keep the cluster administrator kubeconfig on the host
for bootstrap only. Never mount the Docker socket or administrator credentials
in an application container.

The parser namespace enforces Pod Security `restricted` and default-deny
ingress and egress. Each Job has no service-account token, application
credentials or writable application/host mount. Use a private bounded scratch
volume. The selected runtime uses `runc`; it shares the Linux node kernel and
provides per-Job containment, not a strong sandbox.

### Local startup and shutdown contract

Compose cannot express readiness for an external Kind cluster. Before starting
the processing profile, a later bootstrap command must:

1. Use an explicit kubeconfig under a private temporary directory and a unique
   cluster name. It must refuse to use `hub` or any remote context.
2. Create Kind with the default CNI disabled, pod CIDR `192.168.0.0/16`, API
   bind address `127.0.0.1` and the `host.docker.internal` certificate SAN.
   Do not wait for node readiness before installing Calico: without a CNI the
   node is expected to stay `NotReady`.
3. Install pinned Calico 3.33 manifests, wait for Calico and the node to become
   Ready, then apply the restricted namespace, narrow Role and default-deny
   policy. Run positive baseline checks followed by deny checks.
4. Build and load the parser image, provision the scoped credential through
   the external issuer, and provide the worker a read-only credential mount.
   Verify TLS, endpoint access and required RBAC before declaring the worker
   ready. Keep renewal outside the worker's controller permissions.
5. Start Compose only after these checks pass. If the cluster or credential is
   unavailable, fail worker startup/readiness; never fall back to local PDF
   parsing. A single local command should run this preflight before
   `docker compose --profile processing up`.

For shutdown, stop accepting parser work and stop the worker with enough grace
to cancel active Jobs and confirm their deletion. Stop the credential issuer,
remove or revoke its token and delete the disposable cluster. If the worker
dies before cleanup, `activeDeadlineSeconds` and TTL remove orphaned Jobs.
Keep the Compose database and Temporal volumes so local document data and
workflow history survive a runtime restart.

The dispatcher can continue to start Temporal workflows while the worker is
unavailable, so bootstrap the runtime before Compose. If the runtime later
goes down, activities wait or retry under their bounded policies; no activity
should report success until the validated result is persisted. On worker
restart, preserve the activity names and order, recognize a result already
persisted before a crash, and avoid submitting duplicate expensive OCR work.
Persist only a small activity summary so PDF bytes and extracted text never
enter Temporal history. These are integration requirements; the current
worker has not been configured for this lifecycle.

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

## Controller connection configuration spike

The [standalone connection prototype](../../spikes/parser-runtime-connection/README.md)
defines explicit endpoint, namespace, CA-file and token-file inputs. It builds
a fresh Kubernetes client configuration without loading a kubeconfig or ambient
administrator credentials. TLS verification stays enabled, the token is read
again before each request, and errors omit credentials and raw response bodies.
Its separate dependency environment keeps the Kubernetes SDK outside v1.2.0.

The v1.3.0 application now includes a first outbound connection adapter using
the spike's verified Kubernetes Python client version. It accepts only an
explicit local HTTPS endpoint, dedicated namespace, CA file and token file;
constructs a fresh client without ambient kubeconfig, certificate, proxy or
administrator settings; and rereads the token before each request. A bounded
Pod-list request checks controller connectivity. Network and server overload
errors become `ParserRuntimeUnavailable`; TLS, configuration, authentication
and authorization rejections become `ParserRuntimeRejected`. The Temporal
activities preserve that distinction for retry handling.

This adapter is not yet configured or used by the worker. It does not create
Jobs, transfer PDFs, validate parser output, or enforce the final Job template.
The worker still uses local PDF extractors until all three parser entry points
are moved behind the isolated runtime.

The prototype passed host-side live checks with a namespace-scoped controller
identity, and rejected an untrusted CA, invalid token, insufficient permissions
and a temporary extra Secret API grant. A subsequent
[container companion](../../spikes/parser-runtime-connection/CONTAINER.md)
validated a read-only Docker credential volume as UID/GID 10001 on the Compose
network. Its directory used mode 0700 and its files mode 0600; the same SDK
client picked up atomic token replacements and refused a missing token. A
different UID could not read the token.

This runs the standalone prototype in a derivative of the worker image, not
the actual Temporal worker. The subsequent
[credential lifecycle companion](../../spikes/parser-runtime-connection/CREDENTIALS.md)
implements host-side token renewal and session revocation. Delivery into the
Docker volume and deployment supervision remain unimplemented. Neither the
connection checks nor the Role enforce parser Job templates or network
isolation; keep those gates open.

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

### OCR process failures and Temporal retries

The high-entropy image probe exhausted the container cgroup while the parser
process survived and returned the generic non-zero-exit error from Tesseract.
The Kubernetes Job therefore cannot be assumed to report `OOMKilled` for every
OCR memory exhaustion; that reason is available when the container process
itself is killed. Use a reliable runtime signal, such as a change in the
container's cgroup OOM counter when supported, before classifying a failure
specifically as resource exhaustion. If no such signal is available, record a
bounded OCR-engine failure rather than claiming an OOM. Do not include
Tesseract stderr or document content in the result or logs.

The workflow uses a separate two-attempt policy for embedded-text and OCR
activities, with a two-second initial interval and ten-second maximum
interval. `ParserRuntimeUnavailable` maps to a retryable Temporal error; known
PDF content, OCR engine, extraction and output-limit errors map to non-retryable
Temporal errors. These contracts prepare the activities for the parser adapter,
which must report temporary startup or connection failures using
`ParserRuntimeUnavailable`. The current local adapters do not emit that error
yet. A worker must inspect the Job/container outcome, persist a bounded failure
once, and clean up the Job; it must not resubmit the same expensive OCR
operation merely because the parser child returned a non-zero status. Test
child-process OOM separately from a Job container OOM and from an ordinary OCR
timeout.

Before the first failure-policy change, source inspection showed that a
non-zero Tesseract exit became `OcrExtractionFailed` and that all three OCR
attempts could run. The activity regressions check that temporary runtime
unavailability remains retryable and known PDF/OCR failures become
non-retryable without exposing exception details. Workflow regressions check
the bounded parser retry policy and that a terminal non-retryable OCR failure
is recorded once with the OCR stage and bounded failure code, then stops
processing. They verify policy configuration and terminal handling; a live
Temporal retry count still needs verification when the parser adapter is
integrated.

Keep the existing upload-size, page-count, extracted-character, OCR-pixel and
per-page timeout limits. Measure Job CPU, memory, scratch space, startup time
and total deadlines against the synthetic fixtures before choosing numeric
Kubernetes limits. The existing aggregate Compose limits are not a substitute
for per-Job limits.

## Required integration spike before implementation

The disposable infrastructure spike for the selected local topology was run
on 2026-10-18. Existing transport and lifecycle probes provide separate
evidence for these Job behaviors:

1. receive a synthetic PDF up to the configured upload limit over `pods/exec`
   stdin without buffering the entire transfer unexpectedly;
2. return a bounded result up to the configured extraction limit over the exec
   channel, with the correct process exit status and without placing content
   in Job logs or Temporal history;
3. be cancelled, time out and be deleted after both success and failure;
4. run under the proposed namespace-scoped controller permissions while the
   parser Pod has no token and cannot reach another Pod or the Internet.

The worker-shaped route probe reached the Kind API over the project network
with a scoped credential. The actual Temporal worker remains unintegrated.
Do not use `hub` or a remote context. If binary streaming, output bounds,
scoped credentials or cleanup fail when reproduced against the final Job
template, stop and compare a narrowly scoped artifact broker design. Do not
weaken network policy or mount the Docker socket to make the integration
appear to work.

### Initial spike results — 2026-10-17

The disposable Kind 1.37 cluster used Calico 3.33, a dedicated kubeconfig, a
`restricted` namespace and a default-deny ingress/egress policy. The probe Job
was accepted with a non-root UID, read-only root filesystem, dropped
capabilities, `RuntimeDefault` seccomp, bounded `emptyDir`, and automatic
service-account token mounting disabled. The cluster was deleted after the
infrastructure probe. Follow-up resource measurements and an extracted-text
limit correction are recorded below.

| Check | Result | Evidence and limit |
| --- | --- | --- |
| Configured transfer and extraction sizes | Pass at transport level | The Python client 37.0.1 streamed a deterministic 20 MiB file through stdin in 64 KiB chunks; the restricted Pod reported the same byte count and SHA-256. It then returned a JSON envelope containing exactly 1,000,000 ASCII characters (1,000,018 bytes total), collected below a 1,000,100-byte cap, with exit code `0`. This exercises the configured byte and character counts, not the application parser, OCR, Unicode expansion, peak memory or CPU use. Keep a separate encoded-response byte cap because non-ASCII text and JSON escaping can produce a larger payload. |
| Parser resource profile | Measured, single runs | Ran the exact current parser source from `document-platform-api:dev` in disposable containers with network disabled, read-only root, capabilities dropped, no-new-privileges, 1 CPU, 512 MiB memory, 128 PIDs and a 64 MiB `/tmp` tmpfs. The image's three parser module hashes matched the working tree. The one-page digital fixture (1,370 bytes) used 0.044 s wall time and peaked at 41.0 MiB cgroup memory during inspection; embedded-text extraction returned 266 characters in 0.034 s and peaked at 40.6 MiB. Wall and CPU measurements start after Python imports; memory peaks include the interpreter and imported modules. |
| OCR resource profile | Measured, single runs | The one-page scanned fixture (129,112 bytes) returned 243 characters in 0.792 s, with 0.741 s cgroup CPU and a 140.0 MiB cgroup memory peak (39.1 MiB at start). A synthetic 860-byte page at 200 DPI rasterized to 4,472 × 4,472 pixels (19,998,784, below the 20-million-pixel cap) and completed in 1.015 s, with 1.026 s cgroup CPU and a 252.9 MiB memory peak (39.1 MiB at start). A `/tmp` usage sampler polling every 10 ms observed no scratch use; a shorter transient write could be missed. |
| 20 MiB parser input | Measured, synthetic | A valid one-page PDF padded with trailing spaces to exactly 20,971,520 bytes passed inspection (0.512 s, 60.5 MiB cgroup memory peak) and embedded-text extraction (0.094 s, 80.9 MiB peak). It yielded 30 characters. Since most of the file is padding, this measures input size and buffering, not a complex 20 MiB PDF with compressed images or streams. |
| 50-page parser input | Measured, synthetic | A 19,621-byte digital PDF with 50 simple text pages extracted 1,349 characters in 0.025 s and peaked at 41.0 MiB. Running OCR on the same 50 pages at 200 DPI took 11.316 s wall time and 11.297 s cgroup CPU; peak memory was 119.2 MiB (39.1 MiB at start). Both runs stayed below the 512 MiB container limit. |
| Current-source resource rerun | Baseline, single runs, 2026-10-18 | Ran the parser modules from the current worktree, mounted read-only, with dependencies from the existing local image (PyMuPDF 1.28.2, matching `uv.lock`; Tesseract 5.5.0). Each network-disabled container used UID 10001, read-only root, dropped capabilities, no-new-privileges, 1 CPU, 512 MiB memory, 128 PIDs and a 64 MiB `/tmp` tmpfs. The scanned invoice OCR used 0.917 s wall / 0.825 s cgroup CPU and peaked at 142.7 MiB; the 20 MiB padded PDF used 0.117 s / 0.068 s and 60.6 MiB for inspection, then 0.122 s / 0.077 s and 80.7 MiB for text extraction. A 50-page text PDF OCR used 15.904 s / 15.839 s and 108.4 MiB. One page at the 20-million-pixel ceiling used 3.201 s / 3.191 s and 252.7 MiB. A combined 50-page PDF with every page at that raster ceiling used 35.210 s / 35.083 s and 253.9 MiB. All completed below the container limits. These synthetic single runs are baselines, not recommended Job limits; timing excludes container/Python startup and imports, and `/tmp` use was not sampled. |
| Repeated scanned-invoice pages | Pass at 288 MiB, 50 pages, 2026-10-18 | Repeated the repository's one-page `examples/documents/invoice-scanned.pdf` 50 times into a 135,456-byte PDF. Current parser source completed OCR for all pages in 27.001 s wall / 26.763 s cgroup CPU, returned 12,199 characters and peaked at 142,143,488 bytes (about 135.5 MiB). The network-disabled container used UID 10001, read-only root, dropped capabilities, no-new-privileges, 1 CPU, 128 PIDs, a 64 MiB `/tmp` tmpfs and equal 288 MiB memory/swap caps; cgroup OOM and limit counters remained zero. This exercises repeated ordinary scan pages, but the pages are identical and the input is far below the 20 MiB upload limit. It does not cover varied or full-page photographic scans. |
| Lower memory-limit probe | Pass at 288 MiB, single runs, 2026-10-18 | Ran current parser source in separate network-disabled containers capped at 320 MiB and 288 MiB, with read-only root, UID 10001, dropped capabilities, no-new-privileges, 1 CPU, 128 PIDs and a 64 MiB `/tmp` tmpfs. Each run OCRed 50 blank synthetic pages sized to rasterize to 4,471 × 4,471 pixels (19,989,841 pixels per page) at 200 DPI. Both completed all pages; cgroup peaks were 263,340,032 bytes at 320 MiB and 263,352,320 bytes at 288 MiB (about 251 MiB). The 288 MiB run is the lowest limit tried, not a minimum or recommended Job budget. Blank pages, one run per limit and Docker's local runtime do not cover image-heavy PDFs, runtime variation or concurrent Jobs. |
| High-entropy image stress case | OOM at 512 MiB and 768 MiB, one page, 2026-10-18 | A synthetic one-page PDF at the 20 MiB upload limit contained a 4,471 × 4,471 RGB JPEG made from random pixels (18,533,943 bytes before PDF embedding); the page raster was 19,989,841 pixels at 200 DPI. With the current parser source, each network-disabled Docker run used UID 10001, read-only root, dropped capabilities, no-new-privileges, 1 CPU, 128 PIDs and a 64 MiB `/tmp` tmpfs. At both memory caps, cgroup `oom_kill` increased to 1 and the parser returned its generic “Tesseract could not process the page” error. This intentionally pathological noise image is not a representative invoice. It shows that the configured pixel and upload limits alone do not bound Tesseract's memory use for every image; it does not establish the memory needed for normal scans or a final Job budget. The 50-page variant was not run. |
| Kind Job startup, scratch and concurrency | Small baseline, 2026-10-18 | In a separate one-node Kind v1.37 cluster, two sequential restricted Jobs running the combined 50-page/20-million-pixel fixture took 40.5 s and 40.4 s from apply to completion. OCR itself took 36.632 s and 36.072 s; memory peaked at 253.1 and 252.9 MiB. Two concurrent Jobs completed in 42.5 s total; OCR took 38.261 and 38.712 s, with 253.5 and 252.9 MiB peaks. Container start to Python imports-ready was about one second by Kubernetes status timestamps, with the image already loaded. A sampler polling every 10 ms observed 0 bytes under the 64 MiB `/tmp` memory-backed `emptyDir`; it could miss shorter writes. Pods ran as UID 10001 with restricted security context, 1 CPU and 512 MiB memory limit. This was a four-Pod sample on one local node, with no cold image pull; Kind's default CNI did not enforce NetworkPolicy. Results are operational baselines, not capacity guarantees or final resource limits. |
| Four-way concurrency and cold/warm image pull | Small baseline, 2026-10-18 | Four restricted Jobs ran the combined fixture concurrently on one Kind v1.37 node. The group completed in 58.4 s from apply; each OCR took 53.0–53.9 s and peaked at 252.8–259.7 MiB. The 10 ms sampler again observed 0 bytes in `/tmp`. In a separate single-Job check, the node pulled the 154,543,722-byte probe image from a registry bound to localhost and the Kind network in 2.294 s. The cold Job took 7.736 s from apply to completion; the equivalent Job with the image cached took 4.668 s. Both processed the same scanned invoice in about 0.5 s and peaked near 124 MiB. This measures a cold pull over the local Docker bridge, not latency from a remote deployment registry. The local registry setup follows the [Kind guide](https://kind.sigs.k8s.io/docs/user/local-registry/). |
| Extracted-text character limit | Fixed in development | The initial synthetic 50-page PDF returned 1,000,049 characters against a 1,000,000-character limit because page separators were not counted. `PyMuPdfTextExtractor` now counts each separator before checking the limit. Regression tests cover exact-limit acceptance and rejection when separators exceed the limit, including empty pages. Verification against the updated working source rejected the original 50-page case and accepted a 50-page result of exactly 1,000,000 characters. The 2026-10-17 resource measurements predate this correction; the current-source rerun above uses the corrected implementation. |
| Binary stdin | Pass | The Python client 37.0.1 streamed a deterministic 1 MiB payload. After explicitly closing the stdin channel, the parser's SHA-256 matched the sender. A fixed-size reader had previously stopped at its first 64 KiB read, so the parser must consume until EOF rather than assume a read fills the requested buffer. |
| Bounded stdout | Pass, at probe scale | The host collector stopped and closed the stream after 128 KiB while the probe command produced 4 MiB. This demonstrates a consumer-side cap, not the final extraction limit or peak memory use. |
| Process exit status | Pass | Exit code `7` arrived in the exec status channel. |
| Job logs | Pass | A marker returned through exec stdout was absent from the Job container logs. |
| Scoped RBAC | Partial | With a short-lived service-account token, the probe could read/list Pods and create Jobs but could not read Secrets. Exec failed when the role allowed only `get` on `pods/exec`; it worked after granting both `get` and `create` on that subresource. Confirm the required verbs against the exact Kubernetes and client versions used by the application. |
| Selected-topology network policy | Pass for tested IPv4 and service routes, 2026-10-18 | A fresh one-node Kind v1.37.0/Calico 3.33.0 cluster used the project API image in a restricted UID-10001 probe Pod. Before policy it completed TLS 1.3 to `1.1.1.1:443`, resolved an external DNS name, reached a worker-probe Service and accepted a request from that namespace. A default-deny ingress/egress policy then blocked the same IPv4 TLS route, DNS, egress to the worker Service ClusterIP and ingress from the worker probe. The Pod had no IPv6 route (`Network is unreachable` before policy), so IPv6 is not covered. It ran Python's HTTP server, not the PDF parser. This confirms Calico enforcement for the tested routes, not every protocol or host route. See the [selected topology record](pdf-parser-isolation-design.md).
| Disconnect and cancellation | Failure as cancellation | Closing the client WebSocket did not stop the remote child process; it continued and created a marker. A disconnected exec session is therefore not a cancellation mechanism. The controller must delete the Job or invoke an explicit fixed job-control command; `activeDeadlineSeconds` remains the fallback for abandoned Jobs. |
| Job completion and TTL | Pass for success and active deadline | The completion marker let a Job finish, and a short TTL removed the completed Job and Pod. The earlier isolation spike also observed a Job fail with `DeadlineExceeded`, followed by TTL removal of the Job and Pod. This verifies Kubernetes cleanup, not worker-driven cancellation or application error handling; see the [isolation design spike](pdf-parser-isolation-design.md). |
| PID limit | Pass | On a separate Kind 1.37 cluster, both nodes were Ready with `podPidsLimit: 128`. Reading the cgroup hierarchy from the worker showed `pids.max=128` on the Pod parent and `pids.max=9397` on the container cgroup, confirming that the effective Pod limit is 128 without a process-spawn stress test. |
| Worker-shaped connection on Compose project network | Pass for TLS and selected RBAC checks, 2026-10-18 | A non-root `document-platform-api:dev` container with the worker's host-gateway mapping reached the loopback-published Kind API at `host.docker.internal:63354`; TLS hostname and CA verification passed. A temporary ten-minute ServiceAccount token listed Pods in `pdf-parser-probe` (200); Secret access and Pod listing in `worker-probe` were denied (403). The container used a read-only root, dropped capabilities, no privilege escalation, CPU/memory/PID limits and no Docker socket. The project network was created temporarily because the Compose network was absent. This did not start Compose services or the actual Temporal worker. |
| Explicit controller connection configuration | Pass for the standalone host prototype | The standalone spike constructs a fresh Python SDK configuration from a local HTTPS endpoint, namespace, CA file and short-lived token file; a bogus `KUBECONFIG` had no effect. Live checks passed with the scoped Role and rejected an untrusted CA, invalid token (401), insufficient permissions (403) and a temporary extra Secret API grant. Unit checks cover token replacement and loss; the following row records the container credential check. |
| Worker-image credential mount | Pass for the standalone container prototype, 2026-10-18 | A disposable derivative of `document-platform-api:dev` ran as `10001:10001` on the Compose network, with a read-only credential volume (directory 0700, CA/token 0600), no administrator kubeconfig and TLS hostname verification enabled. Writes failed with `EROFS`; UID 10002 could not read the token. The same SDK client refused an invalid replacement token (401), accepted a newly issued token, refused a removed file and resumed after restoration. This verifies Docker-volume ownership and client token reload, not the Temporal worker's integration or an automated renewal mechanism. |
| Controller cleanup and interruption | Pass for the standalone lifecycle prototype, 2026-10-18 | With the scoped Role, synthetic success and parser exit 7 both reached the expected Job terminal state before foreground deletion removed Job and Pod. Deletion used the captured Job UID as a precondition and a fresh REST client after exec. SIGINT during a running synthetic parser removed Job and Pod in 3.69 s; repeated cleanup succeeded. After controller SIGKILL, Kubernetes reported `DeadlineExceeded` and TTL removed both resources, observed 66.54 s after the signal. No Job or Pod remained. See the [lifecycle companion](../../spikes/parser-runtime-connection/LIFECYCLE.md) for commands, offline failure checks and limits. This does not verify Temporal cancellation or real parser execution. |
| Credential provisioning and renewal | Pass for the standalone host prototype, 2026-10-18 | An external provisioner requested short-lived tokens bound to an empty Secret's pinned UID and atomically renewed its private token file. The same SDK client accepted the replacement; the controller could not mint its own tokens. Stopping the provisioner removed the file but did not revoke retained tokens. Deleting the binding made both issued tokens receive HTTP 401, observed after 9.99 s. Recreating its name did not restore the old UID; explicit reprovisioning did restore access. Expiry removal is covered with a controlled clock, not a live wait for server JWT expiry. See the [credential lifecycle companion](../../spikes/parser-runtime-connection/CREDENTIALS.md). Automated delivery into the Docker volume and actual worker integration remain unimplemented. |
| Worker Kubernetes configuration | Not implemented | `worker.py` still constructs local PyMuPDF and Tesseract extractors. `Settings`, `compose.yaml` and `pyproject.toml` define no Kubernetes endpoint, CA, controller token or Kubernetes client dependency. This is expected before the proposed integration; the network smoke test did not run the worker process. |

The transport is promising enough to continue without designing an artifact
broker yet. The selected local network and worker-to-control-plane gates now
have repeatable evidence, but this spike does not clear the full integration gate. These
single-run measurements are baselines, not resource-limit recommendations.
The 20 MiB file is mostly trailing padding, the 50-page PDF uses simple vector
text, and concurrency and adversarial inputs were not measured. The
extracted-text character-limit defect is corrected in the working source and
verified at the exact 1,000,000-character boundary.
The standalone connection, worker-image credential mount and synchronous
controller cleanup contracts are validated. The actual Temporal worker remains
unintegrated. A host-side credential provisioner now validates renewal and
session revocation, with clock-controlled expiry checks. Current-source,
single-run resource baselines now include representative fixtures and combined
page/pixel-limit synthetic OCR. A separate high-entropy image stress case
reached the cgroup OOM limit at both 512 MiB and 768 MiB, despite staying under
the configured upload and per-page pixel limits; it was a pathological noise
image, not a representative invoice. Treat this as evidence that those input
limits do not bound memory for every possible raster, not as a basis for
raising the proposed Job budget without testing representative scans and the
failure behavior in the selected runtime. A 50-page PDF made by repeating the
repository's synthetic scanned invoice completed at a 288 MiB cap with a
135.5 MiB peak; the pages were identical and the file was only 135,456 bytes.
A one-node Kind run also measured Job startup,
`/tmp`, sequential runs, two- and four-Job concurrency, and a cold pull from a
localhost-only registry. Treat these as initial observations only; measure
pulls from the intended deployment registry and repeat under the selected
deployment runtime before choosing numeric Job budgets.
Connect credential delivery to the UID-10001 Docker volume as part of worker
integration.
Later implementation
must connect Temporal cancellation to confirmed Job removal and retain the
deadline/TTL fallback when cleanup cannot run. Preserve the explicit stdin
half-close and bounded streaming behavior in the implementation.

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
- Timeouts, OCR child-process OOM, Job container OOM, ordinary OCR failures,
  oversized results, cancellation, bounded retries and orphan cleanup have
  focused tests using synthetic fixtures. Deterministic failures must not
  trigger repeated OCR attempts for the same PDF.
- Resource limits are based on measurements and the documentation describes
  this as per-Job containment on `runc`, not as a kernel sandbox.

## References

- [Kubernetes Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Kubernetes security contexts](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/)
- [Kubernetes Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
- [Kubernetes Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Kubernetes process ID limits](https://kubernetes.io/docs/concepts/policy/pid-limiting/)
- [Kubernetes Python client](https://github.com/kubernetes-client/python)
