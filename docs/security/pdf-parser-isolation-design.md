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
that justifies operating a separate job runtime. If no suitable runtime can be
run reproducibly without exposing broad host-control credentials to the API or
worker, stop at the existing local-only boundary and keep parser isolation
documented as a limitation.
