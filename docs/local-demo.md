# Local Demo and Operations

Commands run from the repository root unless stated otherwise. The complete
Compose demo is the shortest path. Host development runs the API, dispatcher,
worker and console in separate terminals.

- [Complete processing demo](#complete-processing-demo)
- [Optional local model](#optional-local-model)
- [Host prerequisites](#host-prerequisites), [API](#host-api),
  [dispatcher and worker](#host-dispatcher-and-worker),
  [console](#host-operator-console)
- [HTTP upload and status](#http-upload-and-status)
- [Metrics](#metrics), [retention](#retention-and-blob-auditing),
  [storage configuration](#storage-and-configuration)
- [Container details](#application-containers) and
  [failure demonstration](#local-failure-demonstration)

## Complete Processing Demo

For the complete local processing path, start the separate `processing` profile:

```bash
docker compose --profile processing up --build -d
docker compose --profile processing ps
```

This adds Temporal, its database and UI, the dispatcher, worker and a built
operator console. Open the console at `http://localhost:8088`; its `/api`
requests are proxied to the API within Compose. The dispatcher waits for
migrations and a healthy Temporal server; the worker shares the API's document
volume. The Temporal UI is at `http://localhost:8233`. Set `CONSOLE_PORT`,
`API_PORT`, `POSTGRES_PORT`, `TEMPORAL_PORT` or `TEMPORAL_UI_PORT` if a host port
is occupied. Published application, database and Temporal ports bind to
`127.0.0.1`. This stack uses development credentials and does not provide
production authentication or deployment configuration. The review form uses
the loopback-only demo token `local-only-demo-review-token-change-before-exposure`
unless `DOCUMENT_PLATFORM_REVIEW_OPERATOR_TOKEN` overrides it in `.env`.

After starting the `processing` profile, verify the complete path through the
console's reverse proxy:

```bash
uv sync --all-groups
uv run python scripts/verify_processing_compose.py
```

Use `--base-url http://127.0.0.1:18088` if the console was started with
`CONSOLE_PORT=18088`. The command creates one synthetic PDF and retains its
document record in the local database. It checks upload, embedded-text
extraction, invoice classification and the final review-required status. This
is a manual local smoke test, not part of the default CI pipeline. It prints a
direct console link for the verified document; the
[v0.9 local demo walkthrough](runbooks/v0.9-demo.md) uses that link.
For three reusable examples (digital invoice, scanned invoice and unrelated
report), see the [synthetic demo documents](../examples/documents/README.md). The
optional local-model proposal and human approval path is covered by the
[v1.0 verification record](runbooks/v1.0-verification.md#local-ai-assisted-review).

## Optional Local Model

Ordinary processing works without Ollama. To enable advisory proposals in
Compose, start Ollama on the host with the configured model available, then
recreate the processing stack from the repository root:

```bash
DOCUMENT_PLATFORM_OLLAMA_ENABLED=true \
  docker compose --profile processing up --build -d
```

The default model reference is `qwen3:8b`; override
`DOCUMENT_PLATFORM_OLLAMA_MODEL_REFERENCE` when using a different local model.
For a host-run worker, set `DOCUMENT_PLATFORM_OLLAMA_ENABLED=true` in its
environment or `.env` before starting it. Proposals remain separate from the
rule-based extraction and cannot approve an invoice.

The model adapter classifies provider timeouts, unavailability and invalid
response envelopes using safe error codes. The workflow makes at most two
provider attempts within a five-minute total bound, then records the safe
terminal code without changing document status. Invalid response envelopes
are non-retryable; malformed invoice JSON content is saved as an `INVALID`
proposal. The per-worker model concurrency limit is one by default.
Repository writes serialize on the processing run so a proposal and a failure
cannot both be stored through the application.

For a host-run worker, the default Ollama URL is `http://localhost:11434`. In
Compose, the worker uses `http://host.docker.internal:11434`; set
`OLLAMA_COMPOSE_BASE_URL` if Ollama is reachable at a different address. The
Compose stack does not start or download a model server.

## Host Prerequisites

- Python 3.13 and `uv`;
- Docker with the Compose plugin;
- Node.js 24 and pnpm 11.23.0 for the development console;
- Tesseract with English language data for a host-run OCR worker. Verify the
  installation with `tesseract --list-langs`; the default language is `eng`.
  Command, language, raster DPI, per-page pixel limit and per-page timeout are
  configurable in `.env` for a host-run worker.
  The Compose image already contains Tesseract and English data.
  `DOCUMENT_PLATFORM_TESSERACT_MAX_PAGE_PIXELS` defaults to 20,000,000 and is
  also forwarded to the Compose worker. The limit is checked at the configured
  DPI before allocating each page image. Pages above it fail OCR processing;
  raise it only when the worker has sufficient resources. Ordinary A4 pages
  at the default 200 DPI use approximately 3.9 million pixels.

## Host API

For source preview, review and reprocessing, configure the shared token before
starting the API. Set these values in the API terminal or in `.env`, and use the
same token in the console:

```bash
export DOCUMENT_PLATFORM_REVIEW_OPERATOR_TOKEN='replace-with-at-least-32-characters'
export DOCUMENT_PLATFORM_REVIEW_OPERATOR_ID='local-reviewer'
```

The console sends the token for protected source-preview, review-resolution
and reprocessing requests and never persists it. This is a development fixture,
not a per-user identity or authorization system.

Start the API in the same terminal:

```bash
uv sync --all-groups
docker compose up -d postgres
uv run alembic upgrade head
uv run uvicorn document_platform.bootstrap:app --reload --no-access-log
```

The API is available at `http://localhost:8000`. Current endpoints:

- liveness: `GET http://localhost:8000/health/live`;
- readiness: `GET http://localhost:8000/health/ready`;
- Prometheus metrics: `GET http://localhost:8000/metrics`;
- document ingestion: `POST http://localhost:8000/api/v1/documents`;
- operator queue: `GET http://localhost:8000/api/v1/documents?queue=ACTIVE|REVIEW|FAILED|UNSUPPORTED&limit=25&offset=0`;
- document status: `GET http://localhost:8000/api/v1/documents/{document_id}`;
- source PDF: `GET http://localhost:8000/api/v1/documents/{document_id}/source`
  (review bearer token required; local demo only; the review console fetches it
  on demand from the review panel);
- review resolution: `POST http://localhost:8000/api/v1/documents/{document_id}/review-resolution`;
- controlled reprocessing: `POST http://localhost:8000/api/v1/documents/{document_id}/reprocessing-requests`;
- OpenAPI document: `GET http://localhost:8000/openapi.json`;
- interactive API documentation: `http://localhost:8000/docs`.

Document status includes `current_run.ai_execution` with the persisted AI
state (`DISABLED`, `RUNNING`, `COMPLETED` or `FAILED`) and timestamps. A null
value means no recorded execution, not disabled; historical runs and runs
that have not entered the activity can both have no record. The console displays
this state in the AI comparison panel. Its periodic polling continues while
recorded AI is running, with a six-minute window from its recorded start and
a 30-second start grace period for newly finalized invoices with no AI record.
Older unknown/running states retain manual refresh. See the
[execution contract](architecture.md#advisory-execution-contract).

## Host Dispatcher and Worker

The optional local Temporal profile is independent from the application
PostgreSQL instance. Start it alone when working on workflow handoff or
inspecting workflow execution history outside the full `processing` profile:

```bash
docker compose --profile temporal up -d
```

Temporal listens on `localhost:7233`; its local UI is available at
`http://localhost:8233`. When running the API on the host instead of in the
`processing` profile, start the dispatcher separately so HTTP uploads remain
available when Temporal is being restarted:

```bash
uv run python -m document_platform.dispatcher
```

Start the processing worker in a third terminal after the API and dispatcher:

```bash
uv run python -m document_platform.worker
```

The worker starts the document and its processing run atomically, then extracts
embedded text with bounded PyMuPDF processing. Each extraction is immutable and
keyed by its processing run, so a Temporal activity retry reuses the persisted
result instead of repeating the work. A deterministic, configurable threshold
marks low-text documents as `OCR_RECOMMENDED`. Only those runs execute bounded
Tesseract OCR and persist an immutable OCR result; activity retries reuse it.
The workflow then persists the selected canonical source and its reason, so
downstream stages receive a traceable input. It classifies that selected text
using a small deterministic, word-boundary keyword policy. For invoices, it
extracts explicitly labelled fields, checks required values and a positive
total, and persists the decision. `AUTO_APPROVE` atomically transitions the
document to `APPROVED` and the run to `COMPLETED`; `REVIEW_REQUIRED` transitions both to review. The
workflow marks unknown and non-invoice documents `UNSUPPORTED` while completing
their run. The console exposes the classification reason and stops polling for
that terminal run. A configured local review operator can then approve or reject the review-required document. Resolution is
atomic, immutable and idempotent for the same decision, reviewer and note.

## Host Operator Console

Run the operator console in a separate terminal, starting from the repository root:

```bash
cd apps/operator-console
pnpm install --frozen-lockfile
pnpm dev
```

Vite serves the development console at `http://localhost:5173` and proxies
`/api` requests to the backend at `http://localhost:8000` by default. Override
the development target with `VITE_API_PROXY_TARGET` when required. The Compose
console is a separate static build served by unprivileged NGINX, not Vite.
Open `/system-map` in either console to inspect the implemented local components
and their source references. This map is static documentation, not live health
or a trace of an individual document. Its document journey compares automatic
approval, manual review and failure with reprocessing using persisted-state
semantics; it does not replay a particular run.
The page also links to the exported OpenAPI contract, ADRs, model evaluation,
operational metrics, verification runbook and current security limitations in
this repository. Those links require repository access while it is private.

## HTTP Upload and Status

Upload a PDF with a client-generated idempotency key:

```bash
curl --request POST http://localhost:8000/api/v1/documents \
  --header 'Idempotency-Key: example-upload-001' \
  --form 'document=@supplier-invoice.pdf;type=application/pdf'
```

Successful acceptance returns `202 Accepted`. Repeating the same request returns
the original identifiers with `replayed: true`; reusing the key for different
content returns `409 Conflict`.

The status endpoint returns public document metadata and the most recently queued
processing run, including bounded stage/code evidence when that run has failed.
Its optional `processing_output` contains only extraction counts,
quality decisions, canonical-text selection, classification, invoice fields and
validation reason codes. Internal storage paths and extracted text are never
exposed by the HTTP contract.

When an invoice run has an advisory AI result, `current_run.ai_proposal` contains
the structured fields, validation issues, and model provenance. A terminal
provider error appears instead in `current_run.ai_proposal_failure` as a bounded
code (`TIMEOUT`, `UNAVAILABLE` or `INVALID_RESPONSE`). Both fields are `null`
when no outcome is recorded, including when Ollama is disabled or work is still
in progress. The deterministic `processing_output` remains authoritative.
The status endpoint is unauthenticated in this local demo, so use synthetic
documents only; neither raw document text nor prompts are returned.
After deterministic processing finishes, the console continues polling while
recorded AI execution is running, for up to six minutes from its recorded start.
A newly finalized invoice without an AI record has a 30-second start grace
period. Disabled, completed or failed AI execution stops periodic updates once
deterministic processing is terminal. Manual refresh remains available; see the
[advisory execution contract](architecture.md#advisory-execution-contract).

## Metrics

`GET /metrics` exposes Prometheus text metrics for local operational scraping.
It records build information plus completed HTTP request counts and durations,
and refreshes a PostgreSQL snapshot of processing-run counts by current status
and oldest queued-run age on every scrape. Labels are limited to method, matched
route template, HTTP status class and the bounded processing-run status enum;
document identifiers, filenames, tokens, request URLs and document content are
never labels. The endpoint is operational infrastructure, not part of the
versioned `/api/v1` business contract.

Every completed HTTP response also carries `X-Correlation-ID`. A safe client
value is preserved; otherwise the API generates a UUID. The identifier is
request-scoped operational metadata and never replaces a document or processing
run identifier.

Application logs are emitted as one JSON object per event. HTTP completion logs
contain only the correlation ID, method, matched route template, status and
duration; raw URLs, headers, document values and credentials are excluded. The
custom request event replaces Uvicorn's access log, hence the local command uses
`--no-access-log`.

Start the optional local monitoring stack after the API is listening on port
`8000`:

```bash
docker compose --profile observability up -d prometheus grafana
```

Prometheus is available at `http://localhost:9090`. Its target page should show
`document-platform-api` as `UP`. Useful initial queries are
`document_platform_processing_runs`,
`document_platform_processing_queue_oldest_age_seconds` and
`rate(document_platform_http_requests_total[5m])`.

Grafana is available at `http://localhost:3000` with the local-only credentials
`admin` / `local-development-only`. Its provisioned **Document Platform
Operations** dashboard shows scrape health, current run states, oldest queued-run
age, request rate and p95 latency. Dashboard and datasource changes belong in
`ops/observability/grafana`; UI edits are intentionally disabled because
version-controlled files are authoritative. The Compose profile retains local
time-series and Grafana data and is not a production monitoring setup.
Both observability ports bind to `127.0.0.1` in Compose.

## Retention and Blob Auditing

Preview documents eligible for retention without modifying the database or
local blob storage:

```bash
uv run python -m document_platform.retention --retention-days 90
```

The preview includes only `APPROVED`, `REJECTED` and `FAILED` documents whose
`status_changed_at` is strictly earlier than the cutoff. It reports counts and
stored byte totals. To delete eligible document records and their database-
owned processing evidence, add `--apply`. This does not delete filesystem
blobs; blob garbage collection remains disabled until upload coordination is
implemented and concurrency-tested. Deletion commits each batch separately;
after an interrupted run, repeat the command to process remaining eligible
documents. Its summary counts only documents deleted during that run.

Report possible unreferenced local blobs without modifying storage:

```bash
uv run python -m document_platform.blob_audit --min-age-hours 24 --scan-limit 1000
```

The report checks canonical published blobs older than the specified age
against PostgreSQL and prints aggregate counts only. It counts staged
`.upload` files in `temporary` and `incoming` separately and reports how many
are older than the same threshold, with their combined size. Older staged files
are only possible crash remnants. `scan_truncated=true` means the results cover
only part of storage. Even a complete report does not authorize file deletion:
uploads and the audit do not share a per-blob lock yet.

## Storage and Configuration

PostgreSQL uses local-only credentials from `compose.yaml`. Copy `.env.example`
to `.env` only when overriding defaults. Alembic is the only schema owner;
application startup never creates or modifies tables.

Local document blobs are written below `data/` by default and are excluded from
Git. Override the root with `DOCUMENT_PLATFORM_STORAGE_ROOT` and the 20 MiB
upload limit with `DOCUMENT_PLATFORM_MAX_DOCUMENT_BYTES`. PDF inspection rejects
invalid, encrypted and over-limit files; the default page limit is 50 and can be
set through `DOCUMENT_PLATFORM_MAX_DOCUMENT_PAGES`.

## Application Containers

Build the shared API/worker image from the locked production dependencies:

```bash
docker build -t document-platform-api:dev .
docker run --rm --entrypoint id document-platform-api:dev
```

The runtime uses UID/GID `10001`, includes English Tesseract data and has a
writable `/app/data` directory. The default command starts the API; the image
also contains the worker module and Alembic migrations.

Compose drops all Linux capabilities and enables no-new-privileges for API,
console, dispatcher, migrations and worker. Each has explicit CPU, RAM, swap
and PID budgets. The worker defaults to 2 CPUs, 1 GiB RAM with no additional
swap, and 256 PIDs including threads. See the
[budget table and runtime verification](runbooks/v1.1-container-restrictions.md).
These are starting values for the local synthetic demo; concurrent or larger
workloads require measurement. To change a memory budget in a Compose override,
update both `mem_limit` and `memswap_limit` if swap should remain disabled.
Compose restrictions do not apply to a host-run worker or standalone
`docker run` command.

To run the containerized API with PostgreSQL, migrations and persistent local
document storage:

```bash
docker compose --profile app up --build -d api
docker compose --profile app ps
```

The API is at `http://localhost:8000`; set `API_PORT` if that host port is in
use. Compose waits for healthy PostgreSQL, applies Alembic migrations, then
starts the API. Its healthcheck calls `/health/ready`. Stop only the API with
`docker compose --profile app stop api`. To stop the entire Compose project,
use `docker compose down` without `-v` so database and document volumes remain.
The dispatcher and worker are not started by this profile, so uploads can be
registered but will not be processed until those separate processes are running.

## Local Failure Demonstration

To exercise terminal retry handling without an upstream dependency, start only
the worker with the local fault injection enabled:

```bash
DOCUMENT_PLATFORM_FAULT_INJECTION_STAGE=EMBEDDED_TEXT_EXTRACTION \
  uv run python -m document_platform.worker
```

The embedded-text activity fails on each of Temporal's three attempts. The
workflow then records `ACTIVITY_RETRY_EXHAUSTED`, marks the processing run and
document as `FAILED`, and remains failed in Temporal. Unset the variable before
starting a normal worker, then use the authenticated reprocessing endpoint to
create a new run.
