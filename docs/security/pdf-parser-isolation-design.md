# PDF Parser Isolation Design

Status: design complete; no parser isolation is implemented.

## Decision for the current release

Keep v1.2.0 scoped to the local single-operator demo. Do not add a disposable
parser runtime to the Compose stack in this release. The current loopback-only
boundary, synthetic documents and application-container limits remain the
accepted scope; they do not make hostile PDFs safe to process.

Parser isolation is a worthwhile separate learning project only if a runtime
that can create and destroy a restricted job per document is selected first.
A subprocess in the existing API or worker container can improve crash
recovery, but it is not a security sandbox: it shares the container's user,
environment, filesystem, network and aggregate resource limits.

## Current parsing boundary

PDF parsing happens in more than one service:

1. `POST /api/v1/documents` calls `PyMuPdfInspector.inspect` through
   `AcceptDocumentUploadHandler` before the blob is registered. The API process
   opens the uploaded PDF to check encryption, structure and page count.
2. The Temporal worker opens the PDF again in
   `PyMuPdfTextExtractor` for embedded text.
3. When OCR is needed, `TesseractPdfOcrExtractor` opens the PDF with PyMuPDF,
   rasterizes each page and starts Tesseract with the generated PNG bytes.

Moving only OCR to a sidecar would leave both upload-time inspection and
embedded-text extraction in the API/worker trust boundary. Any complete design
must account for all three paths.

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

## Runtime candidate for a future prototype

For a portfolio prototype on this Mac, use a separately named `kind` cluster
with Calico and run one Kubernetes Job per parsing request. Kubernetes Jobs
provide a one-off Pod lifecycle, a deadline and a retry limit. Calico can
enforce the default-deny ingress and egress policy required for parser Pods.
Apply a restricted Pod security context as well: non-root UID, no privilege
escalation, read-only root filesystem, dropped capabilities, the runtime's
default seccomp profile, bounded resources and no service-account token. See
[Kubernetes Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/),
[Kubernetes security contexts](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/)
and [Calico on kind](https://docs.tigera.io/calico/latest/getting-started/kubernetes/kind).

This candidate is a job-containment exercise, not a claim of stronger
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
timed out. This verifies ingress enforcement. Egress denial still needs a
separate check during implementation.

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

This option is not part of v1.2.0. It may become a separate v1.3.0 development
track after v1.2.0 is closed if a concrete portfolio goal justifies operating
the runtime. The infrastructure spike confirmed that Kind with Calico can be started and
used for these checks on this machine. Do not change the project version as part of
this documentation update.

## Required changes if the work is resumed

Before implementation, choose and validate the job runtime on the target
development environment. Then design one end-to-end vertical slice that:

- removes native PDF inspection from the API request path, or routes it
  through the same isolated job boundary;
- moves embedded-text extraction, rasterization and OCR behind that boundary;
- sends at most the configured upload limit to a job and returns bounded
  structured output, without logging PDF bytes, extracted text or secrets;
- gives the parser job no database, Temporal or operator-token credentials;
- provides no external network route and no writable host or application data
  mount beyond its private scratch space;
- enforces per-job CPU, memory, process-count and wall-clock limits, and
  destroys the job and scratch data after success or failure;
- handles malformed input, timeout, out-of-memory termination, process crash,
  output overflow and runtime unavailability without wedging the worker or
  repeating an expensive hostile job indefinitely;
- records a safe, bounded failure outcome while keeping the existing document
  and processing history consistent.

The numeric resource budgets must be measured against the supported synthetic
fixtures and the selected runtime. Do not infer a safe memory budget only from
the compressed PDF size or page count.

## Scope and stop condition

Do not implement this design as part of v1.2.0. Reopen it if the project takes
untrusted PDFs, runs on a shared host, or has a concrete portfolio objective
that justifies operating a separate job runtime. If the isolated Kind/Calico
spike is not reproducible, or if its controller requires broad host-control
credentials in the API or worker, stop at the existing local-only boundary and
keep parser isolation documented as a limitation.
