# PDF Parser Isolation Integration Proposal

Status: embedded-text/OCR worker flow and Temporal cancellation/restart have
live evidence on a disposable Compose + Kind/Calico stack. A repeatable local
Kind/Calico bootstrap and issuer supervisor are implemented with a disposable
egress baseline/deny check. The supervised Compose command passed service
startup, orderly shutdown and a synthetic scanned-invoice workflow. The direct
base host bind-mount credential path remains unusable; the sync-service volume
path is implemented. In the v1.3.0 implementation, upload inspection no longer
opens PDFs in the API and page count is recorded with the first isolated text
extraction. The migration has been applied to a fresh database and the
asynchronous upload path has live verification. The complete unit suite passed
543 tests on 2026-10-20. As of 2026-10-24, the focused Temporal replay test
passes 16 checked-in histories: two branches from each release with this
workflow (v0.6.0–v1.2.0) plus invoice and other-document histories recorded
from v1.3.0-dev. Releases v0.1.0–v0.5.0 predate the Temporal workflow. Live
Kind checks distinguish a container OOM from an ordinary OCR error.

This proposal refines the parser-isolation work described in the
[isolation design](pdf-parser-isolation-design.md). The local single-operator
v1.2.0 release is closed. The separate [v1.3.0 scope](../releases/v1.3.0.md)
tracks the selected local runtime for the portfolio exercise; follow-up
validation outside that local scope is listed there.

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
volume. A namespace-scoped Kubernetes `ValidatingAdmissionPolicy` binds the
allowed Job template to this namespace. It checks the parser image, command,
single-container shape, scratch-only volume, token setting, security context,
labels and Job deadlines; `ResourceQuota` enforces the shared aggregate CPU,
memory and ephemeral-storage ceiling. The local API server must enable the
`ValidatingAdmissionPolicy` admission plugin. The selected runtime uses `runc`;
it shares the Linux node kernel and provides per-Job containment, not a strong
sandbox.

### Local startup and shutdown contract

Compose cannot express readiness for an external Kind cluster. The repository
command `uv run --no-sync python scripts/parser_runtime.py up` now performs this
preflight before starting the processing profile:

1. Use an explicit kubeconfig under a private temporary directory and a unique
   cluster name. It must refuse to use `hub` or any remote context.
2. Create Kind with the default CNI disabled, pod CIDR `192.168.0.0/16`, API
   bind address `127.0.0.1` and the `host.docker.internal` certificate SAN.
   Do not wait for node readiness before installing Calico: without a CNI the
   node is expected to stay `NotReady`.
3. Install pinned Calico 3.33 manifests, wait for Calico and the node to become
   Ready, then apply the restricted namespace, narrow Role, parser Job
   admission policy and default-deny network policy. Run positive baseline
   checks followed by deny checks. The `verify` subcommand also runs this stage
   alone and removes its disposable cluster.
4. Build and load the parser image, provision the scoped credential through
   the external issuer, and provide the worker a read-only credential volume.
   Compose now waits for a credential-sync service to validate and populate
   that volume; the host issuer remains outside Compose and renews the source
   files. Verify TLS, endpoint access and required RBAC before declaring the
   worker ready. Keep renewal outside the worker's controller permissions.
5. Start Compose only after these checks pass. If the cluster or credential is
   unavailable, fail worker startup/readiness; never fall back to local PDF
   parsing. The `up` command supervises Compose and retains its named data
   volumes during shutdown. Startup, a synthetic upload workflow, orderly
   shutdown and interrupted-run cleanup passed live checks on 2026-10-19.

For shutdown, stop accepting parser work and stop the worker with enough grace
to cancel active Jobs and confirm their deletion. Stop the credential issuer,
remove or revoke its token and delete the disposable cluster. If the worker
dies before cleanup, `activeDeadlineSeconds` and TTL remove orphaned Jobs.
Keep the Compose database and Temporal volumes so local document data and
workflow history survive a runtime restart.

The dispatcher can continue to start Temporal workflows while the worker is
unavailable, so bootstrap the runtime before Compose. If the runtime later
goes down, activities wait or retry under their bounded policies; no activity
should report success until the validated result is persisted. A live restart
test stopped the worker during a 40-page OCR Job. The parser Job remained until
its active deadline and TTL removed it within 185 seconds. After the OCR
activity's five-minute start-to-close timeout, Temporal retried on the
restarted worker and persisted one OCR extraction row. This recovered the
workflow but repeated OCR work. A separate live test now crashes the worker
immediately after OCR persistence but before activity completion. Temporal
retries the activity as attempt 2 after the five-minute start-to-close timeout;
the handler reuses the persisted row, does not create another parser Job, and
the workflow completes with one OCR row. The focused replay suite passes 16
checked-in histories from v0.6.0 through v1.3.0-dev; it does not cover every
possible execution history. Keep the activity names and order, persist only
small activity summaries, and keep PDF bytes and extracted text out of Temporal history. The
cancellation test added lightweight activity
heartbeats and confirmed that explicit workflow cancellation removed an active
parser Job in 4.8 seconds.

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
non-empty body and byte limit. The current implementation no longer opens the
PDF there. Structural, encrypted-file and page-limit errors therefore become
asynchronous processing failures after the API returns `202 Accepted`. The
document status and failure stage must make that outcome clear in the console.

## Data model for asynchronous inspection

The previous upload path required a page count before registering a document.
The parser cannot provide that value until the worker starts the first Job.
The v1.3.0 implementation represents the count as unknown while the document
is queued:

- `Document.page_count`, `RegisterDocument` and the status API field allow
  `null` until embedded-text extraction succeeds.
- The database constraint allows `NULL` or a positive page count; existing
  counts are preserved and zero is not used as a placeholder.
- The first extraction stores its page count in the same transaction as the
  extraction. Later results are rejected if they disagree with a known count.
- The console shows an unavailable value while the count is unknown, and the
  generated TypeScript API client reflects the nullable field.

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

The application controller creates one restricted Job,
waits for its owned Pod, streams the PDF to a fixed parser command and collects
bounded binary stdout. It signals the PID 1 supervisor with a fixed completion
command, observes the terminal Job condition and deletes the Job with a UID
precondition in a `finally` path. The Job manifest has no application volume,
database or Temporal credentials, Kubernetes API token, operator token or
service port; it mounts only private bounded scratch storage. It uses the
Pod Security `restricted` fields, `backoffLimit: 0`, a deadline and TTL.

The parser command accepts only the two fixed operations, reads one bounded PDF
from stdin and emits one versioned JSON result with the input digest, page
count, text and character counts. It returns a generic non-zero status on
invalid input or a result over its encoded-byte limit. The trusted worker
adapter validates the exact result schema, protocol version, operation, input
digest, page count, text length and character counts before persistence.
Commands use fixed argument vectors; never interpolate filenames, PDF values or
other user input into a shell command. Do not use the Docker socket, host paths,
ConfigMaps or Secrets as PDF transport, and do not use logs as the result
channel.

The Temporal worker uses the isolated adapter for embedded-text extraction
and OCR. It requires an explicit local API endpoint, namespace, CA file, scoped
token file and parser image, verifies the API before opening the database, and
fails startup when this configuration is missing or refused. Compose requires
the same settings and mounts the private credentials directory read-only only
in the worker. The API no longer performs upload-time PDF inspection in the
v1.3.0 implementation; the first embedded-text Job now provides that structural
check. The nullable page-count migration and upload flow passed a live run with
a fresh isolated Compose database: a valid synthetic PDF was accepted with
`202`, first observed without a page count, then persisted with one page; a
malformed PDF was accepted with `202` and failed asynchronously while its page
count remained unknown. The host could not resolve the pinned Calico manifest
host during that run, so the pinned manifests came from a temporary local
cache. Focused replay now passes 16 histories, and live Compose/Kind evidence
covers transient parser-runtime recovery; permanent node loss, multi-node
recovery and deployment-runtime validation remain outside the local checks.

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
exact stdin/stdout behavior, exit status, cancellation and memory use were
proven in the standalone spike and exercised in the integrated controller.
Retain the bounded streaming behavior. See the
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
  namespace quota and a cap on concurrent parser activities. The controller
  enforces two Jobs per process with a bounded semaphore. The disposable
  runtime bootstrap now applies a namespace `ResourceQuota` that allows the
  combined requests and limits of two Jobs at the current settings, so multiple
  worker processes share the same aggregate compute and ephemeral-storage
  budget. A quota rejection is classified as temporary runtime unavailability
  for Temporal retry. The bootstrap checks the installed quota values; a live
  saturation probe is now part of `parser_runtime.py verify`: it submits three
  restricted full-budget Pods and requires the third admission to fail for this
  quota, then deletes the probes. This passed live on 2026-10-20: two Pods were
  admitted, the third was rejected, and cleanup removed the probes and disposable
  cluster. The host could not resolve the pinned Calico manifest host, so the
  same pinned files were fetched through Docker Desktop's proxy for this run.
  Keep quota values aligned with the per-Job settings when those budgets change;
  this check establishes resource admission, not production capacity.

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

Focused unit tests cover the restricted Job manifest, bounded binary transport,
strict result validation, non-zero parser exits, UID-guarded cleanup and parser
command protocol. On 2026-10-18, the application controller and parser CLI ran
embedded-text and OCR Jobs in a fresh Kind v1.37.0/Calico 3.33.0 cluster. DNS
and IPv4 TLS to `1.1.1.1:443` succeeded before the namespace policy; both were
blocked after applying default-deny ingress and egress. The scoped controller
token created and executed Jobs, while authorization checks denied Pod creation
and Secret access. Both Jobs returned the expected synthetic result and the
controller removed each Job and Pod. The probe ran from the host using the
namespace token, not from the Compose worker or Temporal. The embedded-text and
OCR results were then wired into the Temporal worker. The current Job settings
use 512 MiB memory request and 1 GiB limit; this smoke run is not a resource
stress test or a final budget. At the time of this smoke check, upload-time
inspection still ran locally; the current source has since removed that API
call, but the replacement flow has not been live-verified.

The prototype passed host-side live checks with a namespace-scoped controller
identity, and rejected an untrusted CA, invalid token, insufficient permissions
and a temporary extra Secret API grant. A subsequent
[container companion](../../spikes/parser-runtime-connection/CONTAINER.md)
validated a read-only Docker credential volume as UID/GID 10001 on the Compose
network. Its directory used mode 0700 and its files mode 0600; the same SDK
client picked up atomic token replacements and refused a missing token. A
different UID could not read the token.

This section records the standalone prototype before it was integrated into
the actual Temporal worker. The subsequent
[credential lifecycle companion](../../spikes/parser-runtime-connection/CREDENTIALS.md)
implements host-side token renewal and session revocation. The later supervised
Compose runtime now delivers credentials through the UID-10001 volume and
manages startup and shutdown. Neither the original connection checks nor the
Role enforce parser Job templates or network isolation; the namespace admission
policy and Calico checks documented below enforce those separate boundaries in
the local runtime.

## Result contract

The parser CLI returns one versioned JSON object with `protocol_version`,
`operation`, `input_sha256`, `page_count`, `text`, `character_count` and
`non_whitespace_character_count`. The worker must reject results with an
unsupported protocol version, malformed JSON,
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

The network-disabled Docker probe observed the cgroup `oom_kill` counter rise
while the parser returned Tesseract's generic non-zero result. In the live
Kind/Calico run, the same high-entropy fixture at 512MiB ended with Pod
`reason: OOMKilled`; at 768MiB, real Tesseract returned an ordinary OCR error
and the OOM counter did not rise. A synthetic child allocator at 768MiB also
ended with `OOMKilled`. The controller now uses the Pod termination reason to
classify container OOM, and a counter delta as a best-effort process-level
signal only when the container remains available. The cgroup counter is
container-scoped and does not identify a PID. In Kubernetes' default cgroup v2
configuration, `memory.oom.group` kills the container's tasks together, so
these live tests cannot attribute the initiating OOM to Tesseract specifically.
If the runtime exposes no reliable signal, preserve a bounded OCR-engine
failure rather than claiming an OOM. Do not include Tesseract stderr or document
content in the result or logs. See the [Kubernetes cgroup v2 behavior note](https://kubernetes.io/blog/2026/10/06/kubernetes-cgroups-v2-shift/) and the [Linux cgroup v2 memory controller documentation](https://www.kernel.org/doc/html/v6.5/admin-guide/cgroup-v2.html).

The workflow uses a separate two-attempt policy for embedded-text and OCR
activities, with a two-second initial interval and ten-second maximum
interval. `ParserRuntimeUnavailable` maps to a retryable Temporal error; known
PDF content, OCR engine, extraction and output-limit errors map to non-retryable
Temporal errors. These contracts require the parser adapter to report temporary
startup or connection failures using `ParserRuntimeUnavailable`. The local
adapter maps runtime startup and connection failures to this retryable outcome;
a real Compose/Kind outage test observed it on the first embedded-text attempt
before recovery on retry. The worker inspects the Job/container outcome,
persists a bounded failure once and cleans up the Job; deterministic OCR
failures do not trigger repeated parser work. The selected cgroup v2 runtime
reports group OOM, so classify the container outcome without attributing it to
a specific child process.

Before the first failure-policy change, source inspection showed that a
non-zero Tesseract exit became `OcrExtractionFailed` and that all three OCR
attempts could run. The activity regressions check that temporary runtime
unavailability remains retryable and known PDF/OCR failures become
non-retryable without exposing exception details. Workflow regressions check
the bounded parser retry policy and that a terminal non-retryable OCR failure
is recorded once with the OCR stage and bounded failure code, then stops
processing. They verify policy configuration and terminal handling; Compose +
Kind now provides a live retry, cancellation and post-persistence crash
recovery baseline. The focused replay suite passes 16 checked-in histories,
while permanent node loss and multi-node recovery remain unverified.

Keep the existing upload-size, page-count, extracted-character, OCR-pixel and
per-page timeout limits. Local synthetic measurements informed the current
per-Job requests, limits and aggregate quota, which remain provisional. Compose
container limits are not a substitute for per-Job limits, and the local results
do not establish capacity for a broader corpus or a deployment runtime.

## Live parser Job and integration verification

The disposable infrastructure spike and application controller smoke check for
the selected local topology ran on 2026-10-18. Existing transport and lifecycle
probes plus the current Job controller provide evidence for these behaviors:

1. receive a synthetic PDF up to the configured upload limit over `pods/exec`
   stdin without buffering the entire transfer unexpectedly;
2. return a bounded result up to the configured extraction limit over the exec
   channel, with the correct process exit status and without placing content
   in Job logs or Temporal history;
3. be cancelled, time out and be deleted after both success and failure;
4. run under the selected namespace-scoped controller permissions while the
   parser Pod has no token and cannot reach another Pod or the Internet.

The worker-shaped route probe reached the Kind API over the project network
with a scoped credential. The actual Temporal worker also ran in the isolated
Compose stack against Kind, verified access at startup, and processed a
synthetic image-only PDF through embedded-text and OCR Jobs under default-deny
network policy. The workflow persisted OCR text and completed with
`REVIEW_REQUIRED`; parser Jobs and Pods were removed. The PDF's synthetic text
markers were absent from Temporal history and API/worker logs.

Cancellation and worker restart were tested against active OCR Jobs. A workflow
cancel removed its Job in 4.8 seconds after activity heartbeats were added. A
worker stop left the Job for deadline/TTL cleanup (observed within 185 seconds);
the five-minute activity timeout then caused Temporal to retry on the restarted
worker and persist one OCR row. A separate controlled crash after OCR persistence
now confirms activity retry reuses that row and does not create another parser
Job. Do not use `hub` or a remote context. Do not weaken network policy or mount
the Docker socket to make the integration appear to work.

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
| Parser Job admission boundary | Pass in disposable Kind v1.37.0, 2026-10-24 | The bootstrap enables the `ValidatingAdmissionPolicy` API-server plugin, labels the dedicated namespace, and installs a namespace-scoped binding with `failurePolicy: Fail` and `validationActions: Deny`. The policy type-checks without CEL warnings. Server-side dry runs using the production controller's generated embedded-text and OCR Jobs were admitted; ten unsafe variants across those paths were rejected by this policy, including a different image, an extra container, a hostPath volume, service-account token mounting and a command override. `ResourceQuota` separately enforces the aggregate CPU, memory and ephemeral-storage ceiling, and the same full bootstrap verified two full-budget Pods pass while a third fails quota. This is local single-node admission evidence; cluster administrators can still change or remove the policy, and it does not establish production capacity or kernel isolation. |
| Configured transfer and extraction sizes | Pass at transport level | The Python client 37.0.1 streamed a deterministic 20 MiB file through stdin in 64 KiB chunks; the restricted Pod reported the same byte count and SHA-256. It then returned a JSON envelope containing exactly 1,000,000 ASCII characters (1,000,018 bytes total), collected below a 1,000,100-byte cap, with exit code `0`. This exercises the configured byte and character counts, not the application parser, OCR, Unicode expansion, peak memory or CPU use. Keep a separate encoded-response byte cap because non-ASCII text and JSON escaping can produce a larger payload. |
| Parser resource profile | Measured, single runs | Ran the exact current parser source from `document-platform-api:dev` in disposable containers with network disabled, read-only root, capabilities dropped, no-new-privileges, 1 CPU, 512 MiB memory, 128 PIDs and a 64 MiB `/tmp` tmpfs. The image's three parser module hashes matched the working tree. The one-page digital fixture (1,370 bytes) used 0.044 s wall time and peaked at 41.0 MiB cgroup memory during inspection; embedded-text extraction returned 266 characters in 0.034 s and peaked at 40.6 MiB. Wall and CPU measurements start after Python imports; memory peaks include the interpreter and imported modules. |
| OCR resource profile | Measured, single runs | The one-page scanned fixture (129,112 bytes) returned 243 characters in 0.792 s, with 0.741 s cgroup CPU and a 140.0 MiB cgroup memory peak (39.1 MiB at start). A synthetic 860-byte page at 200 DPI rasterized to 4,472 × 4,472 pixels (19,998,784, below the 20-million-pixel cap) and completed in 1.015 s, with 1.026 s cgroup CPU and a 252.9 MiB memory peak (39.1 MiB at start). A `/tmp` usage sampler polling every 10 ms observed no scratch use; a shorter transient write could be missed. |
| 20 MiB parser input | Measured, synthetic | A valid one-page PDF padded with trailing spaces to exactly 20,971,520 bytes passed inspection (0.512 s, 60.5 MiB cgroup memory peak) and embedded-text extraction (0.094 s, 80.9 MiB peak). It yielded 30 characters. Since most of the file is padding, this measures input size and buffering, not a complex 20 MiB PDF with compressed images or streams. |
| 50-page parser input | Measured, synthetic | A 19,621-byte digital PDF with 50 simple text pages extracted 1,349 characters in 0.025 s and peaked at 41.0 MiB. Running OCR on the same 50 pages at 200 DPI took 11.316 s wall time and 11.297 s cgroup CPU; peak memory was 119.2 MiB (39.1 MiB at start). Both runs stayed below the 512 MiB container limit. |
| Current-source resource rerun | Baseline, single runs, 2026-10-18 | Ran the parser modules from the current worktree, mounted read-only, with dependencies from the existing local image (PyMuPDF 1.28.2, matching `uv.lock`; Tesseract 5.5.0). Each network-disabled container used UID 10001, read-only root, dropped capabilities, no-new-privileges, 1 CPU, 512 MiB memory, 128 PIDs and a 64 MiB `/tmp` tmpfs. The scanned invoice OCR used 0.917 s wall / 0.825 s cgroup CPU and peaked at 142.7 MiB; the 20 MiB padded PDF used 0.117 s / 0.068 s and 60.6 MiB for inspection, then 0.122 s / 0.077 s and 80.7 MiB for text extraction. A 50-page text PDF OCR used 15.904 s / 15.839 s and 108.4 MiB. One page at the 20-million-pixel ceiling used 3.201 s / 3.191 s and 252.7 MiB. A combined 50-page PDF with every page at that raster ceiling used 35.210 s / 35.083 s and 253.9 MiB. All completed below the container limits. These synthetic single runs are baselines, not recommended Job limits; timing excludes container/Python startup and imports, and `/tmp` use was not sampled. |
| Repeated scanned-invoice pages | Pass at 288 MiB, 50 pages, 2026-10-18 | Repeated the repository's one-page `examples/documents/invoice-scanned.pdf` 50 times into a 135,456-byte PDF. Current parser source completed OCR for all pages in 27.001 s wall / 26.763 s cgroup CPU, returned 12,199 characters and peaked at 142,143,488 bytes (about 135.5 MiB). The network-disabled container used UID 10001, read-only root, dropped capabilities, no-new-privileges, 1 CPU, 128 PIDs, a 64 MiB `/tmp` tmpfs and equal 288 MiB memory/swap caps; cgroup OOM and limit counters remained zero. This exercises repeated ordinary scan pages, but the pages are identical and the input is far below the 20 MiB upload limit. It does not cover varied or full-page photographic scans. |
| Repeatable Docker and Kind parser benchmark | Pass, 2026-10-20 | `scripts/benchmark_parser_resources.py` runs supplied fixtures in disposable Docker containers with no network, read-only root and source mount, UID 10001, dropped capabilities, no-new-privileges, bounded PIDs, CPU, memory and `/tmp`; it reports JSON metrics without extracted text and removes each container on exit. A temporary Kind v1.37/Calico 3.33 cluster then ran the same parser image and `process_pdf` function in restricted Jobs with a default-deny policy. The egress probe was blocked before these Jobs ran. The exact generated 50-page repeated scanned-invoice PDF was 6,425,211 bytes; both runtimes returned 12,199 characters for 50 pages. Docker at a 512 MiB limit peaked at 441,856,000 and 442,142,720 bytes (about 421.4 and 421.7 MiB); Kind at 512 MiB peaked at 441,245,696 bytes (420.8 MiB), and at 1 GiB peaked at 447,688,704 bytes (426.8 MiB). All four Docker/Kind executions completed without OOM. Docker OCR wall/CPU measurements were 21.815/21.642 and 21.754/21.602 seconds; Kind parser wall/CPU measurements were 24.580/24.392 seconds at 512 MiB and 23.829/23.625 seconds at 1 GiB. The Kind wall/CPU figures exclude cluster, Pod startup and stdin transfer; exec wall time including transfer was about 24 seconds. The Kind container retained a small waiting Python process while the parser ran through Kubernetes exec, matching the controller's exec pattern. The 10 ms Docker `/tmp` sampler saw no use; Kind scratch usage was not sampled. This is one synthetic document, image and local runtime, with sequential runs. The Kind and Docker peaks agree closely for this fixture, but the result is not a final resource budget. The 2026-10-18 report recorded a 142,143,488-byte (about 135.5 MiB) peak at a 288 MiB cap for a 135,456-byte repeated-page PDF. That historical artifact is much smaller than the 6,425,211-byte fixture generated now, so the old result is not a byte-identical comparison and the remaining memory difference is unresolved. |
| Repeated scanned-invoice OCR across memory limits | Pass, three sequential Docker runs per limit, 2026-10-20 | `scripts/benchmark_parser_resources.py` repeated the checked-in `invoice-scanned.pdf` page to 50 pages and ran the current `document-platform-api:dev` parser image with network disabled, read-only root, UID 10001, 1 CPU and a 64 MiB `/tmp` tmpfs. All nine runs returned 50 pages and 12,199 characters with no parser failure or OOM. At 512 MiB, peaks were 468,639,744, 441,995,264 and 441,810,944 bytes (446.9, 421.7 and 421.5 MiB); OCR wall times were 25.267, 23.581 and 24.911 s. At 768 MiB, peaks were 441,700,352, 441,610,240 and 442,023,936 bytes (421.2–421.6 MiB), with 23.333–25.791 s wall times. At 1 GiB, peaks were 441,888,768, 441,905,152 and 442,085,376 bytes (421.5–421.7 MiB), with 24.029–25.790 s wall times. The peak variation across larger limits was small; the first 512 MiB run was higher, but still completed with about 65 MiB headroom. This representative scanned fixture supports the current 1 GiB default as a conservative provisional setting; it does not establish capacity for varied user documents or change the high-entropy OOM evidence at 512 MiB. Docker measurements do not replace a repeated end-to-end Kind/Temporal comparison. |
| Synthetic camera-style scanned invoices | Pass, three sequential Docker runs per fixture at 1 GiB, 2026-10-21 | Generated three distinct one-page invoice PDFs, raster-only at 1,653 × 2,339 pixels (3,866,367 pixels per page), with variable paper tone, edge shadow, scanner speckle, varied invoice fields and JPEG compression. `scripts/benchmark_parser_resources.py` ran each three times with network disabled, read-only root, UID 10001, 1 CPU and a 64 MiB `/tmp` tmpfs. All nine OCR runs completed with one page and stable per-fixture output counts: 532, 527 and 530 characters. Per-run cgroup peaks ranged from 110,362,624 to 136,699,904 bytes (105.2–130.4 MiB); eight runs were between 105.2 and 105.4 MiB, while the first run of fixture A reached 130.4 MiB. OCR wall time was 0.921–1.307 s, and the 10 ms `/tmp` sampler observed no use. These are synthetic photo-style scans, not camera photographs or a representative corpus; each is one page, so this does not establish multipage memory behavior. The pathological high-entropy PDF remains a separate stress case. |
| Varied photo-style multipage OCR across memory limits | Pass, three sequential Docker runs per limit, 2026-10-21 | Generated an 8,130,078-byte, image-only PDF with 50 distinct grayscale invoice pages at 1,653 × 2,339 pixels (3,866,367 pixels per page, 200 DPI), varied invoice content, paper tone, edge shadows and scanner-like speckle. The current `document-platform-api:dev` parser image ran through `scripts/benchmark_parser_resources.py` with network disabled, read-only root, UID 10001, 1 CPU and a 64 MiB `/tmp` tmpfs. All nine OCR runs completed with 50 pages and 26,353 characters; no run was OOM-killed. At 512 MiB, cgroup peaks were 366,018,560, 365,690,880 and 366,342,144 bytes (348.8–349.6 MiB), with 32.871–33.663 s wall time. At 768 MiB, peaks were 366,891,008, 366,395,392 and 366,301,184 bytes (349.3–349.8 MiB), with 33.183–34.844 s wall time. At 1 GiB, peaks were 365,957,120, 366,198,784 and 365,756,416 bytes (348.7–349.1 MiB), with 34.012–36.910 s wall time. Peaks include the interpreter and imported modules. This synthetic photo-style fixture is not a set of camera photographs or a representative corpus; nine sequential runs on one local Docker runtime do not establish capacity or final per-Job budgets. The high-entropy stress case remains separate. |
| Concurrent varied photo-style multipage OCR across memory limits | Pass, three concurrent pairs per limit, 2026-10-21 | The prior fixture had been removed, so this comparison used a regenerated 10,683,601-byte image-only PDF with the same stated characteristics: 50 distinct grayscale invoice pages, each 1,653 × 2,339 pixels at 200 DPI, varied invoice content, paper tone, edge shadows and scanner-like speckle. It is not byte-identical to the sequential fixture above. `scripts/benchmark_parser_resources.py` ran six containers per limit with concurrency 2; each container had network disabled, read-only root, UID 10001, a 1 CPU limit and a 64 MiB `/tmp` tmpfs. All 18 OCR runs completed with 50 pages and 67,706 characters, without OOM. At 512 MiB, peaks were 359,178,240, 359,079,936, 358,453,248, 359,325,696, 360,808,448 and 359,325,696 bytes (341.8–344.1 MiB), with 59.894–62.628 s per-container OCR time. At 768 MiB, peaks were 359,030,784, 359,120,896, 358,936,576, 359,342,080, 359,067,648 and 359,333,888 bytes (342.2–342.6 MiB), with 60.946–63.960 s. At 1 GiB, peaks were 360,574,976, 359,227,392, 358,584,320, 359,211,008, 359,170,048 and 359,337,984 bytes (341.9–343.8 MiB), with 65.481–67.714 s. The higher wall time than the sequential profile is consistent with two one-CPU containers competing for local CPU; this Docker run does not represent Kind or production throughput. Memory peaks include the parser interpreter and imported modules. The results show no OOM at these limits for this synthetic fixture but do not set a final budget or demonstrate capacity for other documents or runtimes. |
| Concurrent uploads through Compose, Temporal and Kind parser Jobs | Pass, two 50-page scans, 2026-10-21 | In a fresh Compose project and disposable Kind v1.37.0/Calico 3.33.0 cluster configured with `DOCUMENT_PLATFORM_PARSER_JOB_MEMORY_LIMIT_MIB=768`, two simultaneous API uploads of the checked-in 129,112-byte `invoice-scanned.pdf` repeated to a 135,456-byte, 50-page PDF each returned HTTP 202. The real dispatcher and Temporal worker processed both workflows through restricted parser Jobs under default-deny egress. Both ended `REVIEW_REQUIRED`; the persisted OCR metadata reported 50 pages and 12,199 characters per document. The OCR result timestamps were 2026-10-21 05:50:02.299Z and 05:50:03.267Z (0.968 s apart), strong indirect evidence that the long OCR executions overlapped. This run did not capture a direct count of simultaneously active OCR Pods or per-Job memory peaks. The runtime's IPv4 TLS probe passed before default deny and was blocked afterward; a quota check admitted two full-budget Jobs and rejected the third. Host DNS could not resolve `raw.githubusercontent.com`; the three pinned Calico 3.33.0 manifests were fetched via Docker Desktop's proxy and supplied to the unchanged runtime module in memory. The supervised shutdown removed the dedicated cluster and credential files; `docker compose down --volumes` removed this test project's containers, network and volumes, leaving only the pre-existing `hub` cluster. |
| Concurrent varied uploads at 512 MiB with direct OCR Pod and cgroup sampling | Pass, two 50-page scans, 2026-10-23 | In a fresh Compose project and disposable Kind v1.37.0/Calico 3.33.0 cluster configured with `DOCUMENT_PLATFORM_PARSER_JOB_MEMORY_LIMIT_MIB=512`, two simultaneous uploads of a regenerated 10,653,618-byte image-only PDF with 50 varied grayscale invoice scans each returned HTTP 202. The real API, dispatcher, Temporal worker and restricted parser Jobs processed both through OCR under verified default-deny egress. Both documents reached `REVIEW_REQUIRED` with 50 OCR pages and 82,608 characters each. A host-side Kubernetes watch on `parser.platform/run` in `pdf-parser-probe` directly observed two running OCR Pods overlapping for 115.1 seconds. Their cgroup `memory.peak` values were 350,597,120 and 360,628,224 bytes (334.4 and 343.9 MiB); the observer sampled 238 and 235 times and each peak includes its `kubectl cat` sampling process. OCR timestamps were 1.985 seconds apart. The namespace quota admitted two full-budget Jobs and rejected a third. The egress baseline passed before default deny and IPv4 TLS was blocked afterward. The temporary Compose project and cluster were removed, leaving only the pre-existing `hub` cluster. This is one concurrent pair and a regenerated fixture; it is not byte-identical to the 768 MiB run recorded below, so the measurements are adjacent observations rather than a controlled memory-limit comparison. |
| Repeated concurrent OCR at 512 and 768 MiB across two matched fixtures | Pass, four pairs per limit, 2026-10-24 | Ran the real Compose API, dispatcher, Temporal worker and restricted Kind v1.37.0/Calico 3.33.0 parser Jobs under default-deny IPv4 egress. At each memory limit, submitted three concurrent pairs of the same 10,537,501-byte, 50-page varied grayscale invoice PDF (SHA-256 `ee55310e5446b3b2981149f03e5a410a7e14a66fa73f4e7bcb361797a88fa566`) and one pair of an 11,111,417-byte, 50-page camera-style grayscale invoice PDF (SHA-256 `93759a97b1b283a30177f27ee3afc871a43af71ac22132a743df1692e8b91e3b`, with mild illumination gradients, speckle and up to 0.35-degree skew). All 16 uploads returned HTTP 202; every workflow reached `REVIEW_REQUIRED`, with 50 OCR pages and 82,669 characters for the varied fixture or 82,785 for the camera-style fixture. In the varied-fixture pairs, 512 MiB cgroup peaks ranged from 329.3 to 351.2 MiB and OCR Pod overlap was 87.23–101.12 seconds; at 768 MiB peaks ranged from 328.6 to 338.2 MiB and overlap was 86.09–93.76 seconds. The camera-style pair peaked at 347.1 and 348.1 MiB at 512 MiB, overlapping for 113.23 seconds; at 768 MiB it peaked at 345.8 and 346.3 MiB, overlapping for 95.91 seconds. Each memory peak includes the host-side `kubectl cat` sampler. The quota probe admitted two full-budget Jobs and rejected a third at each limit. This is eight concurrent pairs on one local Kind node and two synthetic fixtures; it does not establish production capacity or a final memory budget, and the separate pathological high-entropy failure evidence still applies. |
| Matched concurrent varied uploads at 512 and 768 MiB with direct OCR Pod and cgroup sampling | Pass, one pair per limit, 2026-10-24 | Reused the exact same 10,653,618-byte, 50-page image-only PDF at both limits (SHA-256 `e655e30c670bf4e2d54e4cda4cff0458a9daa1a8cd953459cc7ccef239c26225`) through separate fresh Compose + Temporal + Kind v1.37.0/Calico 3.33.0 runs. At each limit, two simultaneous API uploads returned HTTP 202 and both workflows reached `REVIEW_REQUIRED` with 50 OCR pages and 82,608 characters under verified default-deny IPv4 egress; the namespace quota admitted two full-budget Jobs and rejected a third. At 512 MiB, two OCR Pods overlapped for 90.03 seconds and peaked at 347,254,784 and 371,826,688 bytes (331.2 and 354.6 MiB), with 187 and 188 samples. At 768 MiB, they overlapped for 89.2 seconds and peaked at 351,682,560 and 370,900,992 bytes (335.4 and 353.7 MiB), with 190 and 191 samples. Each cgroup peak includes the `kubectl cat` sampler. The maximum peaks differed by about 0.9 MiB, but each limit was tested once with one concurrent pair; this single synthetic fixture is not a capacity result or a final budget recommendation. |
| Concurrent varied uploads with direct OCR Pod and cgroup sampling | Pass, two 50-page scans, 2026-10-23 | In a fresh Compose project and disposable Kind v1.37.0/Calico 3.33.0 cluster configured with `DOCUMENT_PLATFORM_PARSER_JOB_MEMORY_LIMIT_MIB=768`, two simultaneous uploads of a regenerated 10,948,365-byte image-only PDF with 50 varied grayscale invoice scans each returned HTTP 202. The real API, dispatcher, Temporal worker and restricted parser Jobs processed both through OCR under verified default-deny egress. Both documents reached `REVIEW_REQUIRED` with 50 OCR pages and 39,355 characters. A host-side Kubernetes watch on `parser.platform/run` in `pdf-parser-probe` directly observed two running OCR Pods overlapping for 53.93 seconds. Their cgroup `memory.peak` values were 344,211,456 and 346,804,224 bytes (328.3 and 330.7 MiB); the observer sampled 114 and 115 times and each peak includes its `kubectl cat` sampling process. OCR timestamps were 0.210 seconds apart. The namespace quota admitted two full-budget Jobs and rejected a third. The bootstrap preloaded the pinned Calico 3.33.0/operator images and loaded single-platform archives matching the Kind node architecture because the host Docker containerd image store made `kind load docker-image` fail with a missing content digest, while the Kind node could not resolve `quay.io`. The parser namespace was empty after completion; the temporary Compose project and cluster were removed, leaving only the pre-existing `hub` cluster. The reusable [watch-and-sample script](../../scripts/measure_temporal_parser_concurrency.py) records this measurement. |
| Concurrent varied full-page OCR | Pass, two concurrent Jobs and Docker containers, 2026-10-20 | Generated a 4,704,338-byte, 50-page grayscale invoice PDF with unique invoice fields per page. Every page is a full-page 200 DPI raster of 1,653 × 2,339 pixels (about 3.87 million pixels), below the 20-million-pixel per-page cap. Both Docker containers (1 CPU, 1 GiB each, network disabled) and both restricted Kind Jobs (1 CPU, 1 GiB limit and 512 MiB request each) completed 50 pages and returned 24,218 characters, with no OOM. Docker peaks were 379,215,872 and 378,564,608 bytes (about 361.6 and 361.0 MiB); OCR wall/CPU times were 34.553/33.867 and 34.586/33.982 seconds. Kind peaks were 337,350,656 and 341,184,512 bytes (about 321.7 and 325.4 MiB); parser wall/CPU times were 32.569/32.094 and 32.505/32.085 seconds, with both execs overlapping for 32.84 seconds total. The default-deny egress policy was verified before the Jobs. The Kind helper kept each restricted Job Pod alive and invoked the parser through `kubectl exec`; wall time excludes cluster and Pod startup. This is one synthetic text-heavy full-page fixture and a single concurrent pair, not a photographic or high-entropy sample or a capacity result. |
| Lower memory-limit probe | Pass at 288 MiB, single runs, 2026-10-18 | Ran current parser source in separate network-disabled containers capped at 320 MiB and 288 MiB, with read-only root, UID 10001, dropped capabilities, no-new-privileges, 1 CPU, 128 PIDs and a 64 MiB `/tmp` tmpfs. Each run OCRed 50 blank synthetic pages sized to rasterize to 4,471 × 4,471 pixels (19,989,841 pixels per page) at 200 DPI. Both completed all pages; cgroup peaks were 263,340,032 bytes at 320 MiB and 263,352,320 bytes at 288 MiB (about 251 MiB). The 288 MiB run is the lowest limit tried, not a minimum or recommended Job budget. Blank pages, one run per limit and Docker's local runtime do not cover image-heavy PDFs, runtime variation or concurrent Jobs. |
| High-entropy image stress case | OOM at 512 MiB and 768 MiB, one page, 2026-10-18 | A synthetic one-page PDF at the 20 MiB upload limit contained a 4,471 × 4,471 RGB JPEG made from random pixels (18,533,943 bytes before PDF embedding); the page raster was 19,989,841 pixels at 200 DPI. With the current parser source, each network-disabled Docker run used UID 10001, read-only root, dropped capabilities, no-new-privileges, 1 CPU, 128 PIDs and a 64 MiB `/tmp` tmpfs. At both memory caps, cgroup `oom_kill` increased to 1 and the parser returned its generic “Tesseract could not process the page” error. This intentionally pathological noise image is not a representative invoice. It shows that the configured pixel and upload limits alone do not bound Tesseract's memory use for every image; it does not establish the memory needed for normal scans or a final Job budget. The 50-page variant was not run. |
| Concurrent high-entropy OOM and cleanup | Pass, two concurrent Jobs, 2026-10-20 | Generated a one-page PDF with a 4,471 × 4,471 RGB noise image (19,989,841 pixels at 200 DPI), a small vector invoice heading, and total size 15,852,671 bytes, below the 20 MiB input cap. Two concurrent network-disabled Docker containers capped at 1 GiB each returned the parser's generic OCR failure (exit 7), with no OOM signal and peaks of 736,002,048 and 734,056,448 bytes (about 701.9 and 700.1 MiB). Two restricted Kind Jobs capped at 512 MiB each ran concurrently under the verified default-deny egress policy. Both parser execs returned 137; Kubernetes reported `reason: OOMKilled` and exit 137 for both containers. The cgroup had `memory.oom.group=1`, so this is container-level OOM evidence and does not attribute the initiating allocation to Tesseract. The controller's previous live classification test remains the evidence for controller error mapping; this probe exercises the parser Pod directly via exec. Cleanup deleted both Jobs, and a namespace query confirmed zero remaining Pods. This fixture is intentionally pathological noise, not a representative scan or a capacity sample. |
| Kind Job startup, scratch and concurrency | Small baseline, 2026-10-18 | In a separate one-node Kind v1.37 cluster, two sequential restricted Jobs running the combined 50-page/20-million-pixel fixture took 40.5 s and 40.4 s from apply to completion. OCR itself took 36.632 s and 36.072 s; memory peaked at 253.1 and 252.9 MiB. Two concurrent Jobs completed in 42.5 s total; OCR took 38.261 and 38.712 s, with 253.5 and 252.9 MiB peaks. Container start to Python imports-ready was about one second by Kubernetes status timestamps, with the image already loaded. A sampler polling every 10 ms observed 0 bytes under the 64 MiB `/tmp` memory-backed `emptyDir`; it could miss shorter writes. Pods ran as UID 10001 with restricted security context, 1 CPU and 512 MiB memory limit. This was a four-Pod sample on one local node, with no cold image pull; Kind's default CNI did not enforce NetworkPolicy. Results are operational baselines, not capacity guarantees or final resource limits. |
| Four-way concurrency and cold/warm image pull | Small baseline, 2026-10-18 | Four restricted Jobs ran the combined fixture concurrently on one Kind v1.37 node. The group completed in 58.4 s from apply; each OCR took 53.0–53.9 s and peaked at 252.8–259.7 MiB. The 10 ms sampler again observed 0 bytes in `/tmp`. In a separate single-Job check, the node pulled the 154,543,722-byte probe image from a registry bound to localhost and the Kind network in 2.294 s. The cold Job took 7.736 s from apply to completion; the equivalent Job with the image cached took 4.668 s. Both processed the same scanned invoice in about 0.5 s and peaked near 124 MiB. This measures a cold pull over the local Docker bridge, not latency from a remote deployment registry. The local registry setup follows the [Kind guide](https://kind.sigs.k8s.io/docs/user/local-registry/). |
| Extracted-text character limit | Fixed in development | The initial synthetic 50-page PDF returned 1,000,049 characters against a 1,000,000-character limit because page separators were not counted. `PyMuPdfTextExtractor` now counts each separator before checking the limit. Regression tests cover exact-limit acceptance and rejection when separators exceed the limit, including empty pages. Verification against the updated working source rejected the original 50-page case and accepted a 50-page result of exactly 1,000,000 characters. The 2026-10-17 resource measurements predate this correction; the current-source rerun above uses the corrected implementation. |
| Binary stdin | Pass | The Python client 37.0.1 streamed a deterministic 1 MiB payload. After explicitly closing the stdin channel, the parser's SHA-256 matched the sender. A fixed-size reader had previously stopped at its first 64 KiB read, so the parser must consume until EOF rather than assume a read fills the requested buffer. |
| Bounded stdout | Pass, at probe scale | The host collector stopped and closed the stream after 128 KiB while the probe command produced 4 MiB. This demonstrates a consumer-side cap, not the final extraction limit or peak memory use. |
| Process exit status | Pass | Exit code `7` arrived in the exec status channel. |
| Job logs | Pass | A marker returned through exec stdout was absent from the Job container logs. |
| Scoped RBAC | Partial | With a short-lived service-account token, the probe could read/list Pods and create Jobs but could not read Secrets. Exec failed when the role allowed only `get` on `pods/exec`; it worked after granting both `get` and `create` on that subresource. Confirm the required verbs against the exact Kubernetes and client versions used by the application. |
| Selected-topology network policy | Pass for tested IPv4 and service routes, 2026-10-18 | A fresh one-node Kind v1.37.0/Calico 3.33.0 cluster used the project API image in a restricted UID-10001 probe Pod. Before policy it completed TLS 1.3 to `1.1.1.1:443`, resolved an external DNS name, reached a worker-probe Service and accepted a request from that namespace. A default-deny ingress/egress policy then blocked the same IPv4 TLS route, DNS, egress to the worker Service ClusterIP and ingress from the worker probe. The Pod had no IPv6 route (`Network is unreachable` before policy), so IPv6 is not covered. It ran Python's HTTP server, not the PDF parser. This confirms Calico enforcement for the tested routes, not every protocol or host route. See the [selected topology record](pdf-parser-isolation-design.md).
| Application controller, parser Job and egress policy | Pass for synthetic embedded-text and OCR, 2026-10-18 | A fresh one-node Kind v1.37.0/Calico 3.33.0 cluster loaded the current `document-platform-parser:dev` image. The host-side application controller used a namespace-scoped token and the restricted Job template. Before policy, the running parser Job resolved external DNS and completed IPv4 TLS to `1.1.1.1:443`; after applying default-deny ingress/egress to the parser namespace, both checks were blocked. Embedded-text and OCR Jobs each returned the expected protocol, page count and synthetic marker. The controller removed each Job and Pod. RBAC allowed Job creation and `pods/exec`, and denied Pod creation and Secret reads. This does not cover the Compose worker, Temporal cancellation, IPv6 or other network paths.
| Disconnect and cancellation | Failure as cancellation | Closing the client WebSocket did not stop the remote child process; it continued and created a marker. A disconnected exec session is therefore not a cancellation mechanism. The controller must delete the Job or invoke an explicit fixed job-control command; `activeDeadlineSeconds` remains the fallback for abandoned Jobs. |
| Job completion and TTL | Pass for success and active deadline | The completion marker let a Job finish, and a short TTL removed the completed Job and Pod. The earlier isolation spike also observed a Job fail with `DeadlineExceeded`, followed by TTL removal of the Job and Pod. This verifies Kubernetes cleanup, not worker-driven cancellation or application error handling; see the [isolation design spike](pdf-parser-isolation-design.md). |
| PID limit | Pass | On a separate Kind 1.37 cluster, both nodes were Ready with `podPidsLimit: 128`. Reading the cgroup hierarchy from the worker showed `pids.max=128` on the Pod parent and `pids.max=9397` on the container cgroup, confirming that the effective Pod limit is 128 without a process-spawn stress test. |
| Worker-shaped connection on Compose project network | Pass for TLS and selected RBAC checks, 2026-10-18 | A non-root `document-platform-api:dev` container with the worker's host-gateway mapping reached the loopback-published Kind API at `host.docker.internal:63354`; TLS hostname and CA verification passed. A temporary ten-minute ServiceAccount token listed Pods in `pdf-parser-probe` (200); Secret access and Pod listing in `worker-probe` were denied (403). The container used a read-only root, dropped capabilities, no privilege escalation, CPU/memory/PID limits and no Docker socket. The project network was created temporarily because the Compose network was absent. This did not start Compose services or the actual Temporal worker. |
| Explicit controller connection configuration | Pass for the standalone host prototype | The standalone spike constructs a fresh Python SDK configuration from a local HTTPS endpoint, namespace, CA file and short-lived token file; a bogus `KUBECONFIG` had no effect. Live checks passed with the scoped Role and rejected an untrusted CA, invalid token (401), insufficient permissions (403) and a temporary extra Secret API grant. Unit checks cover token replacement and loss; the following row records the container credential check. |
| Worker-image credential mount | Pass for the standalone container prototype, 2026-10-18 | A disposable derivative of `document-platform-api:dev` ran as `10001:10001` on the Compose network, with a read-only credential volume (directory 0700, CA/token 0600), no administrator kubeconfig and TLS hostname verification enabled. Writes failed with `EROFS`; UID 10002 could not read the token. The same SDK client refused an invalid replacement token (401), accepted a newly issued token, refused a removed file and resumed after restoration. This verifies Docker-volume ownership and client token reload, not the Temporal worker's integration or an automated renewal mechanism. |
| Controller cleanup and interruption | Pass for the standalone lifecycle prototype, 2026-10-18 | With the scoped Role, synthetic success and parser exit 7 both reached the expected Job terminal state before foreground deletion removed Job and Pod. Deletion used the captured Job UID as a precondition and a fresh REST client after exec. SIGINT during a running synthetic parser removed Job and Pod in 3.69 s; repeated cleanup succeeded. After controller SIGKILL, Kubernetes reported `DeadlineExceeded` and TTL removed both resources, observed 66.54 s after the signal. No Job or Pod remained. See the [lifecycle companion](../../spikes/parser-runtime-connection/LIFECYCLE.md) for commands, offline failure checks and limits. This does not verify Temporal cancellation or real parser execution. |
| Credential provisioning and renewal | Pass for the standalone host prototype, 2026-10-18 | An external provisioner requested short-lived tokens bound to an empty Secret's pinned UID and atomically renewed its private token file. The same SDK client accepted the replacement; the controller could not mint its own tokens. Stopping the provisioner removed the file but did not revoke retained tokens. Deleting the binding made both issued tokens receive HTTP 401, observed after 9.99 s. Recreating its name did not restore the old UID; explicit reprovisioning did restore access. Expiry removal is covered with a controlled clock, not a live wait for server JWT expiry. See the [credential lifecycle companion](../../spikes/parser-runtime-connection/CREDENTIALS.md). Automated session supervision is tracked separately below. |
| Automated Kind/Calico bootstrap and issuer supervision | Pass, 2026-10-18 and 2026-10-19 | `scripts/parser_runtime.py verify` created a random Kind v1.37.0 cluster with the default CNI disabled, installed Calico 3.33.0, loaded the parser image and waited for Calico and node readiness. A restricted parser-image Pod completed TLS 1.3 to `1.1.1.1:443`; after applying the namespace-wide default-deny policy, the same connection was blocked. The host-side scoped controller probe verified TLS/RBAC, and the supervised issuer completed two short-interval renewals before SIGTERM removed its local token. Cleanup removed the temporary cluster and directory; `kind get clusters` showed only the pre-existing `hub`. A second `up` run rebuilt the images, reached API readiness with all processing services running and started the worker with the verified credentials. Ctrl-C stopped the dispatcher and worker with exit code 0; the sync service removed the token and CA from its volume, the anchor and Kind cluster were deleted, and Compose data volumes remained. The documented demo review token was passed only in the command environment because `.env` had no value; `.env` was not changed. The Temporal UI container returned exit code 2 on stop, although Compose completed shutdown and no processing service remained running. The run did not upload a new document. IPv6 and other egress paths are not covered. |
| Aggregate parser resource quota | Pass, full-budget admission probe, 2026-10-20 | A fresh Kind v1.37.0/Calico 3.33.0 cluster applied the namespace quota. Three restricted Pods each requested 250m CPU, 512 MiB memory and 64 MiB ephemeral storage, with limits of 1 CPU, 1 GiB memory and 128 MiB ephemeral storage. The first two were admitted; the third was rejected with `exceeded quota: parser-job-budget`. Cleanup deleted both admitted Pods and the bootstrap removed the disposable cluster, leaving only the pre-existing `hub`. Host DNS could not resolve `raw.githubusercontent.com`; the pinned Calico manifests were fetched through Docker Desktop's proxy and passed to the unchanged bootstrap code for this run. This verifies Kubernetes resource admission at the current settings, not app-level throughput, production capacity or multiple-node behavior. |
| Temporal worker with parser Jobs in Compose + Kind | Pass for embedded-text, OCR, cancellation and retry after worker restart, 2026-10-18 | A fresh Kind v1.37.0/Calico 3.33.0 cluster used the scoped Role and default-deny ingress/egress. The actual Compose API, dispatcher, Temporal and worker started with explicit endpoint/CA/token settings. A synthetic image-only invoice produced zero embedded characters, 380 OCR characters, selected OCR text, and completed its workflow. Text markers were absent from Temporal history and API/worker logs. Canceling a second workflow during a 40-page OCR Job removed the Job in 4.8 s. Stopping the worker during another 40-page OCR Job left it for `activeDeadlineSeconds`/TTL cleanup within 185 s; after the five-minute activity timeout, Temporal retried on the restarted worker, persisted one OCR row and ended `REVIEW_REQUIRED`. This does not cover the crash window after persistence but before activity completion or historical workflow replay. |
| Supervised Compose upload and parser workflow | Pass for one synthetic scanned invoice, 2026-10-19 | With `scripts/parser_runtime.py up`, the API returned HTTP 202 for `examples/documents/invoice-scanned.pdf`. The real dispatcher and Temporal worker used the isolated embedded-text Job (zero characters) and OCR Job (243 characters), then classified the invoice and ended `REVIEW_REQUIRED` for `MISSING_ISSUE_DATE`. The API exposed that terminal workflow result; no Job or Pod remained in the parser namespace. The documented demo operator token was passed through the command environment only; `.env` was unchanged. The first interrupted run stopped Compose and scrubbed the worker credential volume but left its temporary Kind cluster behind. Cleanup now rechecks and retries deletion after the Compose client exits. A repeated interrupted run stopped all processing services, scrubbed token and CA from the volume, removed its Kind cluster automatically, and left only the pre-existing `hub`. A later separate-project run verified the asynchronous upload path and malformed-PDF failure; it used fresh volumes and preserved both those and the original data volumes. |
| Complete unit test suite | Pass, 543 tests, 2026-10-20 | Includes parser controller, worker, supervisor, OCR activity, process workflow and replay coverage for fourteen checked-in histories from v0.6.0 through v1.2.0. A concurrency test confirms the per-process cap rejects a second operation before Job creation. Unit tests cover cgroup-counter and `OOMKilled` mapping; they do not establish a child-specific live OOM outcome or permanent node-loss recovery. |
| Tesseract PDF OCR integration suite | Pass, 13 tests, 2026-10-19 | `tests/integration/ocr/test_tesseract_pdf_ocr_extractor.py` passed with local Tesseract available. This exercises the OCR extractor integration, not the isolated Kubernetes Job controller or Temporal recovery. |
| Isolated Job execution timeout and cleanup | Pass, 50-page synthetic OCR, 2026-10-19 | The real controller submitted a repeated scanned-invoice PDF to a fresh Kind/Calico cluster with a 2-second execution deadline. It returned bounded `ParserRuntimeUnavailable` and confirmed that no Job or Pod remained. The controller call took 27.3 seconds, including cold Job/Pod startup; this is not a measurement of parser execution time. The test exercises the controller timeout path and cleanup, not the Temporal workflow timeout. |
| High-entropy upload through API and Temporal | Pass for ordinary parser failure at 1Gi, 2026-10-20 | An 18,539,731-byte, one-page high-entropy PDF returned HTTP 202 from the real API with the supervised Compose API, dispatcher and Temporal worker connected to a fresh Kind v1.37.0/Calico 3.33.0 runtime under default-deny parser egress. At the default 1GiB Job limit, OCR failed as an ordinary parser error. The workflow ended `FAILED` at `OCR_TEXT_EXTRACTION`; Temporal recorded one `extract-ocr-text` attempt and `OCR_NON_RETRYABLE_FAILURE` with `non_retryable=true`. The API retained the preceding embedded-text result, while `ocr_text` and downstream classification output were absent. No parser Job or Pod remained. |
| High-entropy upload through API and Temporal | Pass for container OOM at 512Mi, 2026-10-20 | With `DOCUMENT_PLATFORM_PARSER_JOB_MEMORY_LIMIT_MIB=512`, a fresh, separate Compose project uploaded an 18,539,482-byte high-entropy PDF through the real API and reached OCR through Temporal. The real worker observed `ParserContainerMemoryLimitExceeded`; Temporal history recorded one `extract-ocr-text` attempt and `OCR_NON_RETRYABLE_FAILURE` with `non_retryable=true`. The API reached `FAILED` at `OCR_TEXT_EXTRACTION`, retained embedded text, and exposed no OCR or downstream output. Kubernetes reported no remaining parser Job or Pod. The runtime applied a 1Gi aggregate `limits.memory` quota for two 512Mi Jobs; its admission probe allowed two and rejected the third. The isolated Compose containers, four project volumes, network and Kind cluster were removed after the run; only the pre-existing `hub` cluster remained. |
| Varied OCR corpus and matched high-entropy budget comparison | Pass, supervised Compose/Temporal, 2026-10-21 | In a fresh Compose project and Kind v1.37.0/Calico 3.33.0 runtime with `DOCUMENT_PLATFORM_PARSER_JOB_MEMORY_LIMIT_MIB=768`, the real API accepted `invoice-scanned.pdf` (129,112 bytes), a rasterized digital invoice (100,364 bytes), a rasterized equipment report (118,469 bytes), and a synthetic high-entropy PDF (14,750,056 bytes). The first three OCR Jobs completed with 243, 273 and 365 characters respectively; the report then ended `UNSUPPORTED` at document classification, not parser failure. The same byte-identical high-entropy PDF (4,471 × 4,471 RGB noise image; 19,989,841 pixels; 37 embedded characters) was submitted in isolated sessions at 512, 768 and 1024 MiB. At 512 and 768 MiB, the worker returned `ParserContainerMemoryLimitExceeded`; at 1024 MiB, it returned `ParserExecutionFailed` because the parser reported an ordinary failure status, with no OOM classification. Each stress workflow ended `FAILED` at `OCR_TEXT_EXTRACTION` after one `extract-ocr-text` attempt; embedded text remained, but no OCR or downstream result was persisted. The Kind runtime verified IPv4 TLS egress before applying default deny and confirmed it was blocked afterward; at each limit the quota probe admitted two full-budget Jobs and rejected the third. No parser Job or Pod remained after the failures, and the temporary Compose projects, volumes, networks and clusters were removed; only the pre-existing `hub` cluster remained. This shows a threshold difference for this one synthetic stress file, not a representative workload budget: 1 GiB avoided OOM but still did not yield OCR text. The parser image was rebuilt from the same working tree for each isolated session, so this is not a binary-identical image comparison. |
| OOM versus ordinary OCR failure in Kind | Pass for container classification, 2026-10-19 | The real controller sent a 15,852,592-byte high-entropy PDF through the selected default-deny policy. At 512MiB, the Pod terminated with `OOMKilled`; the controller returned `ParserContainerMemoryLimitExceeded` and removed the Job and Pod. At 768MiB, real Tesseract returned exit code 1, the cgroup OOM counter stayed at zero and the controller preserved `ParserExecutionFailed`. A synthetic child allocator at 768MiB also caused the Pod to be group-killed and classified as container OOM. Kubernetes' default cgroup v2 group behavior means this topology does not prove which process first triggered memory exhaustion. |
| Controller output overflow and unavailable API | Pass, synthetic PDF, 2026-10-19; API-loss rerun 2026-10-20 | With the real parser Job controller and a 1-byte exec output cap, a valid embedded-text result was rejected as `ParserOutputExceeded`; no Job or Pod remained. A TLS API connection check against a closed local endpoint returned bounded `ParserRuntimeUnavailable`. During live OCR, stopping only the disposable Kind kube-apiserver for five seconds closed the exec WebSocket; the controller returned bounded `ParserRuntimeUnavailable`, then removed the Job and Pod once the API recovered. This was repeated after the OOM-classification change on 2026-10-20; the fault harness passed and the disposable cluster was removed, leaving only `hub`. |
| Node stop/restart and TTL orphan cleanup | Pass in the same single-node Kind cluster, 2026-10-20 | The real controller ran a 50-page OCR Job while the dedicated Kind control-plane node container was stopped for 40 seconds. The controller returned bounded `ParserRuntimeUnavailable`. After restarting the same node and waiting for it to become Ready, the orphaned Job failed with `BackoffLimitExceeded`; its 60-second `ttlSecondsAfterFinished` removed the Job and Pod without controller deletion. The probe used a 20-second active deadline to keep the test bounded. This verifies recovery across a node-container stop/restart while retaining Kind cluster state; permanent node loss and multi-node/production recovery are not covered. The temporary cluster was removed after verification and only `hub` remained. |
| Temporal crash after OCR persistence | Pass, one synthetic scanned invoice, 2026-10-19 | Enabled the local-only `DOCUMENT_PLATFORM_FAULT_INJECTION_CRASH_AFTER_OCR_PERSISTENCE` failpoint. It exits the worker with code 86 after `ExtractOcrTextHandler` commits its OCR row, before the activity returns. Docker restarted the worker (restart count 1); Temporal retried `extract-ocr-text` as attempt 2 about five minutes after scheduling and completed the workflow. The OCR row count and character total remained `1` and `243` before and after retry. Kind events show exactly one embedded-text Job and one OCR Job, so the retry reused the persisted extraction. Temporal history contains no OCR text payload. The workflow ended `REVIEW_REQUIRED` for the fixture's missing issue date. The focused replay suite now passes 16 histories through v1.3.0-dev as of 2026-10-24. |
| Temporal parser retry classification | Pass, simulated activities on disposable Temporal 1.29.3, 2026-10-24 | `scripts/verify-temporal-parser-retries.py` ran against an isolated Temporal/PostgreSQL Compose project. A retryable `PARSER_RUNTIME_UNAVAILABLE` activity error on attempt 1 succeeded on attempt 2. A deterministic non-retryable OCR activity error made one attempt and recorded one terminal processing failure. This verifies Temporal retry orchestration, not recovery of a real parser runtime after Kubernetes/Compose outage. The temporary Compose project and its volume were removed. |
| Real Compose/Kind parser outage and Temporal recovery | Pass for transient embedded-text failure; short OCR interruption tolerated; prolonged outage exhausted retries, 2026-10-24 | In a fresh supervised Compose project and dedicated Kind v1.37.0/Calico 3.33.0 cluster, a synthetic scanned invoice reached an actual embedded-text parser Job. Pausing the dedicated control-plane container caused the real worker to return `PARSER_RUNTIME_UNAVAILABLE` on `extract-document-text` attempt 1. The control plane was immediately unpaused; Temporal attempt 2 completed embedded extraction, the workflow ran a real OCR Job (243 characters), and the API reached `REVIEW_REQUIRED`. In a separate run, an automated 0.8-second pause began as a 20-page OCR Job appeared; the OCR activity completed on attempt 1 with 4,879 characters and the workflow reached `REVIEW_REQUIRED`, so the interruption did not surface as a Temporal activity failure. A separate control-plane stop/restart during a real OCR Job exceeded the two-attempt retry window and ended `FAILED` with `ACTIVITY_RETRY_EXHAUSTED`; this confirms bounded failure during a longer outage, not recovery from permanent node loss. The upload API returned `202` and left `page_count` null while processing; PDF inspection is deferred to the first embedded-text Job, so there is no separate upload-time parser call to fault. The Compose project, Kind cluster, credential material and temporary kubeconfigs were removed; only the pre-existing `hub` remained. |
| Compose credential bind mount | Direct host-to-worker bind remains unusable on this macOS host | With the host-owned private directory at mode 0700 and CA/token at 0600, UID 10001 in the worker could not read the CA and startup failed closed. `chown` to UID 10001 was unavailable to the unprivileged host user. The selected implementation copies those files through a network-disabled sync service into a UID-10001-owned named volume mounted read-only by the worker. The helper's live delivery check passed, as did credential availability in the supervised worker startup; orderly shutdown removed both files from the named volume. |

The local v1.3.0 implementation and its release gate are complete for the
documented Compose + Kind/Calico portfolio topology. The API stores uploads
without opening PDFs; the worker routes embedded-text extraction and OCR to
restricted per-document Jobs, validates bounded results and persists page count
with the first extraction. The supervised bootstrap, credential delivery and
renewal, cleanup, workflow cancellation and restart behavior have live
verification. These checks do not establish production capacity or strong
kernel isolation. Resource measurements remain baselines, not final budget
recommendations; the high-entropy input can still exhaust the configured
container memory and fail OCR even at 1 GiB. Keep the limits provisional and
evaluate them against a representative corpus and a concrete deployment target
before making capacity claims.

The focused replay suite passes all 16 checked-in histories through
v1.3.0-dev. On 2026-10-24, the manual Temporal retry verifier
([`verify-temporal-parser-retries.py`](../../scripts/verify-temporal-parser-retries.py))
passed against a disposable Temporal 1.29.3 server: a simulated
parser-runtime-unavailable error recovered on attempt 2, and a deterministic
failure stopped after attempt 1. On the same date, a supervised Compose/Kind
run also paused the real parser control plane during embedded-text extraction;
Temporal attempt 1 failed with `PARSER_RUNTIME_UNAVAILABLE`, attempt 2
succeeded after immediate recovery, and the scanned invoice completed OCR. A
longer stop/restart during OCR exhausted both bounded attempts. A host-side
credential provisioner validates
renewal and session revocation, with clock-controlled expiry checks. Current-source,
single-run resource baselines now include representative fixtures and combined
page/pixel-limit synthetic OCR. A separate high-entropy image stress case
reached the cgroup OOM limit at both 512 MiB and 768 MiB, despite staying under
the configured upload and per-page pixel limits; it was a pathological noise
image, not a representative invoice. Treat this as evidence that those input
limits do not bound memory for every possible raster, not as a basis for
raising the Job budget without broader representative workload evidence. A
50-page PDF made by repeating the
repository's synthetic scanned invoice completed at a 288 MiB cap with a
135.5 MiB peak; the pages were identical and the file was only 135,456 bytes.
A repeatable Docker benchmark script now measures the current parser function
with bounded resources and no network. Two Docker runs and two Kubernetes Jobs
on 2026-10-20 processed the same generated 50-page PDF and peaked at about
421–427 MiB; the Docker and Kind results at a 512 MiB cap were close. The older
135.5 MiB report used a much smaller 135,456-byte repeated-page PDF, versus
6,425,211 bytes in the current fixture, so it is not a byte-identical
comparison and the memory difference remains unexplained. Retain the existing
512 MiB request and 1 GiB limit as provisional configuration, not as a budget
recommendation. One concurrent pair completed a synthetic varied full-page
invoice fixture at about 322–362 MiB per worker, with Docker and Kind results
both below the 1 GiB Job limit. Subsequent checks added three photo-style Docker
runs at 1 GiB, a pathological high-entropy fixture across 512 MiB, 768 MiB and
1 GiB, and four concurrent 50-page OCR pairs per limit across varied and
camera-style synthetic scans at 512 MiB and 768 MiB. These samples still do not
establish a capacity budget: the high-entropy input failed OCR even at 1 GiB,
and the photographic fixtures are synthetic. Keep the limits provisional until
a broader representative corpus and a concrete deployment target are
available.
A one-node Kind run also measured Job startup,
`/tmp`, sequential runs, two- and four-Job concurrency, and a cold pull from a
localhost-only registry. Treat these as local observations only; measure pulls
from the intended deployment registry and repeat under the target runtime
before making capacity claims.
The supervised `up` path, worker credential delivery and renewal, the
post-persistence crash window, and replay of the 16 checked-in histories now
have evidence, including retry orchestration against a disposable Temporal
server with simulated parser activity errors. A live Compose/Kind test then
paused the real parser control plane during embedded-text extraction: the first
Temporal attempt failed with `PARSER_RUNTIME_UNAVAILABLE`, and the retry
succeeded after immediate recovery. A longer node stop/restart during OCR
exhausted both bounded attempts. Keep deadline/TTL as the fallback when worker-driven
cleanup cannot run. Preserve the explicit stdin half-close and bounded
streaming behavior in the implementation.

## Implementation status against acceptance criteria

- **Pass, verified locally:** the API and worker do not invoke PDF parsers;
  inspection, embedded-text extraction, rasterization and OCR run in restricted
  Jobs. The upload route returns `202`, and first-parse failures remain
  asynchronous with an unknown page count.
- **Pass, verified locally:** bounded worker-to-Job transfer, result validation,
  persistence, cancellation, Job cleanup, retry behavior and replay compatibility
  are covered by focused tests or the live checks listed above. PDF bytes and
  extracted text stay out of logs and Temporal history.
- **Pass with documented limitation:** parser Jobs have no application
  credentials, network access or Compose data-volume mount. They run under
  `runc` and share the node kernel; this is per-Job containment, not a strong
  sandbox. Group-OOM reports do not identify the initiating process.
- **Follow-up outside the local release gate:** numeric resource limits remain
  provisional. Validate them against a representative corpus and the registry
  and runtime of a concrete deployment before making capacity claims.

## References

- [Kubernetes Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Kubernetes security contexts](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/)
- [Kubernetes Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
- [Kubernetes Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Kubernetes process ID limits](https://kubernetes.io/docs/concepts/policy/pid-limiting/)
- [Kubernetes Python client](https://github.com/kubernetes-client/python)
- [Kubernetes cgroup v2 OOM behavior](https://kubernetes.io/blog/2026/10/06/kubernetes-cgroups-v2-shift/)
- [Linux cgroup v2 memory controller](https://www.kernel.org/doc/html/v6.5/admin-guide/cgroup-v2.html)
