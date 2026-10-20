# PDF Parser Isolation Design

Status: the local v1.3.0 runtime is selected and network-tested. Upload
inspection, embedded-text extraction and OCR run through isolated Jobs in the
current integration. A live Compose + Kind check verified asynchronous upload
and page-count persistence. API outage recovery and TTL cleanup after stopping
and restarting the dedicated single-node Kind control plane also have live
evidence. Permanent node loss, multi-node behavior and broader Temporal replay
remain open.

## Decision for the released v1.2.0

Keep v1.2.0 scoped to the local single-operator demo. Do not add a disposable
parser runtime to the Compose stack in this release. The current loopback-only
boundary, synthetic documents and application-container limits remain the
accepted scope; they do not make hostile PDFs safe to process.

The v1.3.0 project now has a selected local runtime that can create and destroy
restricted Jobs. A subprocess in the existing API or worker container can
improve crash recovery, but it is not a security sandbox: it shares the
container's user, environment, filesystem, network and aggregate resource
limits.

## Decision for v1.3.0 development

Use a separately named local Kind cluster with Calico as the parser Job
runtime. Keep the API, database, dispatcher, Temporal and trusted worker in
Compose. The worker connects to the Kind API through
`host.docker.internal:<published-port>` with TLS verification, a pinned CA and
a short-lived namespace-scoped controller credential. Bind the API server to
host loopback and include `host.docker.internal` in its certificate SAN. The
existing worker service already maps `host.docker.internal` to the host
gateway. Do not mount the Docker socket or an administrator kubeconfig.

Run parser Jobs in a dedicated namespace with Pod Security `restricted`, a
default-deny ingress and egress policy, no service-account token, no
application credentials and no application or host data mounts. Calico on
Kind is the selected local portfolio topology; it is not a claim about a
production Kubernetes deployment. The parser runs with `runc` and shares the
node kernel, so describe the result as per-Job containment.

The topology was exercised on 2026-10-18 in a fresh one-node Kind v1.37.0
cluster with Calico 3.33.0. The Kind node used containerd 2.3.4 on Docker
Desktop ARM64. Kind's default CNI was disabled, with pod CIDR
`192.168.0.0/16`. Calico was installed before waiting for the node to become
Ready. The API server bound `127.0.0.1` on port `63354` for this run and its
certificate included `host.docker.internal`.

Before applying the parser namespace's default-deny policy, a restricted
UID-10001 probe Pod successfully completed TLS 1.3 to `1.1.1.1:443`, resolved
an external DNS name, reached a service in the worker probe namespace, and
accepted an HTTP request from that namespace. After applying the policy with
both ingress and egress and no allow rules, the same IPv4 TLS connection was
blocked, DNS timed out, egress to the worker service ClusterIP was blocked,
and ingress from the worker probe Pod was blocked. The project API image ran a
Python HTTP server for these network checks; this was not a PDF parser Job.

A worker-shaped container connected from a temporary Compose project network
to `host.docker.internal:63354` with TLS hostname and CA verification enabled.
It ran as UID 10001 with a read-only root, dropped capabilities, no privilege
escalation, CPU/memory/PID limits and no Docker socket. A short-lived token for
the namespace-scoped controller ServiceAccount listed Pods in the parser
namespace (HTTP 200); reading Secrets and listing Pods in another namespace
were denied (HTTP 403). The token was passed through stdin for the probe. The
parser Pod had no mounted ServiceAccount token, database URL or Temporal
configuration. This validated the worker-to-control-plane path and selected
RBAC denials in a disposable network; it did not run the Temporal worker or
the Compose services.

The Pod had no IPv6 route (`Network is unreachable` before policy), so the
internet-egress result covers the available IPv4 path only. Repeat the check
for IPv6 if the selected runtime or deployment gains IPv6 connectivity. These
checks prove the tested routes and protocols; they do not prove denial over
every possible protocol or host route. Repeat them against the final Job
manifest and runtime configuration before parser integration.

## Parsing boundary in the released v1.2.0 baseline

PDF parsing happens in more than one service:

1. `POST /api/v1/documents` calls `PyMuPdfInspector.inspect` through
   `AcceptDocumentUploadHandler` before the blob is registered. The API process
   opens the uploaded PDF to check encryption, structure and page count.
2. The Temporal worker opens the PDF again in
   `PyMuPdfTextExtractor` for embedded text.
3. When OCR is needed, `TesseractPdfOcrExtractor` opens the PDF with PyMuPDF,
   rasterizes each page and starts Tesseract with the generated PNG bytes.

This was the v1.2.0 boundary that motivated the v1.3.0 design. In the current
v1.3.0 working tree, upload-time inspection is folded into the existing
embedded-text Job; the API stores the PDF without opening it. The change must
still pass migration and live end-to-end verification.

The present size, page-count, raster-pixel and page-time limits reduce routine
resource use. Compose CPU, memory, swap and PID limits constrain each
application container as a whole. They do not impose a hard per-document
memory or CPU budget, and an activity deadline does not guarantee that native
code running in a thread is terminated.

## Options considered

### Keep parsing in the existing containers

This matches the current local demo and remains the smallest option. A child
process could make native crashes and timeouts easier to recover from, but it
would still share the worker container's identity and access. Use this only as
a reliability improvement; do not describe it as hostile-input isolation.

### Add a long-lived parser service to Compose

A dedicated service with no database credentials, a read-only root filesystem,
temporary scratch storage, no published port and narrow resource limits would
reduce the parser's access to application data. It would still be a persistent
process boundary. A compromised parser could attack services reachable on its
network, and Compose service limits would apply to the container rather than
provide a fresh hard budget for each document. It is not sufficient by itself
to claim per-document sandboxing.

### Create a disposable container for every document

This gives a clearer job lifecycle, but the current Compose application has no
trusted job runtime that creates containers. Mounting the Docker daemon socket
into the API or worker to create them would give that application powerful
control over the Docker host. Docker's documentation warns that access to the
daemon can allow host filesystem access through container mounts. Do not add a
daemon socket to the document-processing services. See [Docker Engine
security](https://docs.docker.com/engine/security/) and [protect access to the
Docker daemon](https://docs.docker.com/engine/security/protect-access/).

### Use an external job runtime with per-job isolation

This is the only option considered here for a future claim of disposable
per-document isolation. A trusted controller would submit a bounded job to a
runtime configured to terminate it and enforce CPU, memory, process and wall
time limits. The parser job would run non-root, without database credentials,
with no network access, a read-only base filesystem and a private temporary
directory. The controller would accept only a small, validated result and
would treat timeout, crash, output overflow and job-start failure as explicit
processing failures.

This requires selecting and operating a supported runtime first. The current
Docker Compose/Docker Desktop setup does not provide this per-document job
boundary on its own. Do not assume that a generic Compose sidecar or a Python
subprocess provides equivalent isolation.

## Selected runtime for the local prototype

The selected local prototype uses a separately named `kind` cluster with
Calico and one Kubernetes Job per parsing request. Kubernetes Jobs
provide a one-off Pod lifecycle, a deadline and a retry limit. Calico can
enforce the default-deny ingress and egress policy required for parser Pods.
Apply a restricted Pod security context as well: non-root UID, no privilege
escalation, read-only root filesystem, dropped capabilities, the runtime's
default seccomp profile, bounded resources and no service-account token. See
[Kubernetes Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/),
[Kubernetes security contexts](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/)
and [Calico on kind](https://docs.tigera.io/calico/latest/getting-started/kubernetes/kind).

This design is a job-containment exercise, not a claim of stronger
kernel-level sandboxing: the default container runtime still shares the Linux
kernel. For a stronger parser boundary, gVisor `runsc` would need to be
configured on the Linux node and selected through a Kubernetes RuntimeClass.
The local Docker Engine reports only its default `runc` runtime, and the usual
`kubectl` context points to a remote production-named cluster. Do not use that
context for this work. The infrastructure spike used a separately named Kind
cluster and an isolated kubeconfig.

The spike used Kind v0.33.0 with Kubernetes v1.37.0 and Calico v3.33.0. A
client pod could reach a parser-labeled HTTP pod before policy was applied;
after a Kubernetes NetworkPolicy denied ingress to that pod, the same request
timed out.

A parser-labeled client pod could reach an HTTP pod in another namespace by
its pod IP. After an egress-only policy with no allowed egress rules was
applied to the client, the same request to that IP timed out. Using the IP
kept DNS out of this check. These results verify Calico enforcement for
ingress and pod-to-pod egress in this temporary cluster. A separate restricted
Pod using the project image successfully established TLS 1.3 to `1.1.1.1:443`
before an egress-only NetworkPolicy was applied, then timed out on the same
connection afterward. The host-side HTTPS baseline to that endpoint also
succeeded. This verifies Calico Internet-egress denial for this disposable
Kind setup, not the final parser runtime topology or every possible route and
protocol.

A restricted Job probe ran as UID 10001 without a service-account token, with
a read-only root filesystem, no privilege escalation, all Linux capabilities
dropped, the default seccomp profile and CPU/memory limits. It terminated
after its active deadline with reason `DeadlineExceeded`. Kubernetes removed
the terminated Pod and Job through `ttlSecondsAfterFinished`. This validates
the basic Job deadline and cleanup behavior; it does not parse a PDF or test
application integration.

The cluster and temporary files were removed after the spike. The existing
local cluster named `hub` was left untouched, and no remote Kubernetes
context was used. Docker Desktop supports local Kubernetes for development
and testing, but this does not establish that a custom `runsc` RuntimeClass is
available. See [Docker Desktop Kubernetes](https://docs.docker.com/desktop/use-desktop/kubernetes/)
and [Kubernetes RuntimeClass](https://kubernetes.io/docs/concepts/containers/runtime-class/).

This option was excluded from the released v1.2.0. The separate
[v1.3.0 development scope](../releases/v1.3.0.md) now tracks this portfolio
exercise. The selected local topology has passed the network and worker
connection probes recorded above. Upload-path verification is complete.
Admission enforcement and recovery from permanent node loss or multi-node
failures remain open.

The proposed application integration, including asynchronous page-count
validation, Job data transfer, controller permissions and acceptance criteria,
is documented in [PDF Parser Isolation Integration Proposal](pdf-parser-integration-proposal.md).

On 2026-10-18, the current application Job controller and parser CLI were run
in a fresh Kind v1.37.0/Calico 3.33.0 cluster. Synthetic embedded-text and OCR
Jobs succeeded under the final restricted Job template. External DNS and IPv4
TLS to `1.1.1.1:443` worked before a namespace-wide default-deny policy and
failed after it was applied. The scoped token created Jobs and used `pods/exec`,
but could not create Pods or read Secrets; the controller deleted both Job and
Pod after each run. The host-side probe did not run inside Compose or Temporal.
See the [integration evidence table](pdf-parser-integration-proposal.md) for
the limits of this check.

## Gates before parser integration

The selected local topology has been validated with synthetic probes. Before
integrating the parser, rerun network and permission checks against the final
cluster bootstrap, namespace policy and Job template. The end-to-end proposal
defines the vertical slice and its acceptance criteria. The implementation
must:

- remove native PDF inspection from the API request path, or route it
  through the same isolated job boundary;
- move embedded-text extraction, rasterization and OCR behind that boundary;
- send at most the configured upload limit to a job and return bounded
  structured output, without logging PDF bytes, extracted text or secrets;
- give the parser job no database, Temporal or operator-token credentials;
- provide no external network route and no writable host or application data
  mount beyond its private scratch space;
- enforce per-job CPU, memory, process-count and wall-clock limits, and
  destroy the job and scratch data after success or failure;
- handle malformed input, timeout, out-of-memory termination, process crash,
  output overflow and runtime unavailability without wedging the worker or
  repeating an expensive hostile job indefinitely;
- record a safe, bounded failure outcome while keeping the existing document
  and processing history consistent.

Single-run container baselines cover representative fixtures and combined
synthetic 50-page/20-million-pixel OCR input. A follow-up one-node Kind run
measured two sequential and two concurrent restricted Jobs: OCR took about
36–39 seconds per Job, memory peaked around 253 MiB, Python imports completed
about one second after container start, and a sampler polling every 10 ms
observed no `/tmp` writes. The image was preloaded, and Kind's default CNI did
not enforce NetworkPolicy. A four-Job run completed in 58.4 seconds; each OCR
took 53.0–53.9 seconds and peaked at 252.8–259.7 MiB. A separate cold pull of
the probe image from a localhost-only registry took 2.294 seconds for the
154,543,722-byte image; a cached-image Job completed in 4.668 seconds versus
7.736 seconds for the cold pull Job. This local bridge measurement does not
represent a remote deployment registry. Full results and limits are recorded
in the [integration proposal](pdf-parser-integration-proposal.md). These are
initial local baselines, not capacity guarantees or resource-limit
recommendations. Measure pulls from the intended deployment registry and
repeat under the selected deployment runtime before setting numeric limits.
Do not infer a safe memory budget only from compressed PDF size or page count.
A 50-page PDF made by repeating the repository's scanned-invoice fixture
completed at a 288 MiB memory cap with a 135.5 MiB peak, while a deliberately
pathological random-pixel page caused a child-process OOM at both 512 MiB and
768 MiB. These results describe different workloads; neither is a final Job
budget. See the [integration proposal](pdf-parser-integration-proposal.md).

## Scope and stop condition

This is a local portfolio exercise for synthetic documents. Do not use it to
approve hostile PDFs, confidential data, shared-host execution or public
hosting. Stop integration if the network deny, scoped credential, bounded
transfer or cleanup behavior cannot be reproduced, or if operating the
controller requires Docker daemon access or broad administrator credentials
inside the API or worker. Keep the existing local-only boundary and document
parser limitations if any of these conditions fail.
