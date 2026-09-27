# AI Document Processing Platform

A local-first platform for extracting, validating, and reviewing structured
data from business documents.

## Status

Development now targets `v0.9.0`; the backend reports `0.9.0.dev0` until that
release is cut. The tagged `v0.8.0` remains a local demonstration release,
not a production deployment.

The [`v0.7.0` tagged release](https://github.com/PietroRussoD/ai-document-processing-platform/tree/v0.7.0),
documented in the [release notes](docs/releases/v0.7.0.md), adds operational
failure handling to the durable document-processing and review flow.
The worker performs bounded embedded-text extraction, local OCR fallback,
canonical-text selection, deterministic document classification and invoice
validation. A complete invoice is automatically approved; an incomplete one is
handed off to review. The console derives a safe timeline from persisted
metadata and never renders extracted document text. The API accepts bounded PDF
uploads through real validation, local blob storage and atomic PostgreSQL
registration.
A read endpoint exposes the current document and processing-run status. The
operator console provides tested PDF selection and submission, including
acceptance identifiers, safe error feedback and polling of the persisted
document and processing-run status. Once available, the same status snapshot
also exposes safe extraction, selection, classification and review-resolution
metadata; it never returns extracted document text or blob paths.

`v0.5.0` exposes low-cardinality Prometheus metrics for requests and durable
pipeline state, returns bounded correlation IDs, and emits allowlisted JSON
application logs. An optional local Prometheus/Grafana profile provides a
version-controlled dashboard without pretending to be a production monitoring
deployment.

`v0.6.0` added controlled reprocessing and an Operations Console backed by
persisted run data. An authenticated reprocessing request creates a new,
immutable run linked to its predecessor; it cannot rewrite past evidence or
create a concurrent active run for the same document.

`v0.7.0` makes processing failure states operationally truthful. Terminal
Temporal activity failures now persist safe stage/code evidence and reconcile
the processing run and document with PostgreSQL before the workflow remains
failed. The status API and console expose the bounded failure stage and code
for the current run. A paginated API exposes active, review and failed work
queues as metadata-only summaries. The operator console can browse these
queues, refresh them and open the existing document detail and review flows.
See the [v0.7.0 release notes](docs/releases/v0.7.0.md). `v0.8.0` adds bounded
database retention, report-only blob auditing, an opt-in local processing
stack and delivery/security checks. Its [release notes](docs/releases/v0.8.0.md)
describe the verified scope and limitations. `v0.9.0` development is targeting
a System Map and reproducible demo walkthrough. Physical blob deletion,
malware scanning and production deployment are not implemented.

## Implemented Technology

- Python 3.13 and `uv`;
- FastAPI and PostgreSQL;
- Prometheus client for local operational metrics;
- PyMuPDF for PDF validation and embedded-text extraction;
- Temporal for durable local workflow execution;
- bounded local Tesseract OCR fallback;
- React and TypeScript for the operator console.

## Planned Extensions

- further local-model comparison after a broader corpus and policy design;
- optional S3-compatible storage and external-provider comparison;
- notifications and reference-safe physical blob garbage collection.

The synthetic, versioned invoice-extraction baseline is documented in
[`docs/evaluation.md`](docs/evaluation.md).

## Architecture

The backend follows pragmatic ports and adapters. Business rules and use cases
do not depend on FastAPI, SQLAlchemy, Temporal, Tesseract, Ollama or filesystem
types. Adapters implement those external boundaries.

```text
HTTP / React -> application use cases -> domain rules
                       |       |
                  PostgreSQL  local storage
```

See [architecture documentation](docs/architecture.md),
[local security and limitations](docs/security-and-limitations.md),
[vulnerability reporting](SECURITY.md) and
[architectural decisions](docs/decisions/). The repeatable release checks are
documented in the [v0.2 verification runbook](docs/runbooks/v0.2-verification.md).
The review-resolution flow is documented in the
[v0.3 verification runbook](docs/runbooks/v0.3-verification.md). Its `v0.4`
correction and local-model verification extension is documented separately in
the [v0.4 verification runbook](docs/runbooks/v0.4-verification.md).
Operational telemetry verification is documented in the
[v0.5 verification runbook](docs/runbooks/v0.5-verification.md).
Controlled reprocessing and immutable run lineage are documented in the
[v0.6 verification runbook](docs/runbooks/v0.6-verification.md).
Failure recording and recovery through a replacement run are documented in the
[v0.7 verification runbook](docs/runbooks/v0.7-verification.md).

The current durable decisions are recorded in
[ADR 0001](docs/decisions/0001-pragmatic-ports-and-adapters.md),
[ADR 0002](docs/decisions/0002-preserve-operator-corrections-separately.md)
and [ADR 0003](docs/decisions/0003-keep-local-models-evaluation-only.md).
Operational telemetry is defined in
[ADR 0004](docs/decisions/0004-expose-low-cardinality-prometheus-metrics.md),
with bounded request correlation covered by
[ADR 0005](docs/decisions/0005-use-bounded-http-correlation-identifiers.md) and
structured application logging by
[ADR 0006](docs/decisions/0006-emit-allowlisted-json-application-logs.md).
Controlled reprocessing and immutable run lineage are defined by
[ADR 0007](docs/decisions/0007-create-immutable-reprocessing-lineage.md).
Terminal workflow failure evidence is defined by
[ADR 0008](docs/decisions/0008-record-safe-terminal-workflow-failure-evidence.md).
Safe document retention and blob garbage-collection boundaries are defined by
[ADR 0009](docs/decisions/0009-use-explicit-safe-document-retention.md).

## Repository Layout

```text
apps/
  operator-console/             # React UI, introduced with the first UI slice
docs/
  decisions/                    # architecture decisions with durable impact
src/document_platform/
  domain/                       # entities, value objects and domain policies
  application/
    commands/                   # write use cases
    queries/                    # read use cases
    ports/                      # interfaces to external boundaries
  adapters/
    inbound/http/               # FastAPI routes and transport mapping
    outbound/                   # PostgreSQL, local storage and PDF validation
  bootstrap.py                  # dependency composition and process startup
tests/
  unit/                         # domain and application behavior
  integration/                  # adapters, database, storage and workflows
  e2e/                          # browser/API journeys when they exist
```

Folders are created with the first behavior that belongs in them. The layout is
intentional; empty packages and placeholder abstractions are not committed.

## Development

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
- operator queue: `GET http://localhost:8000/api/v1/documents?queue=ACTIVE|REVIEW|FAILED&limit=25&offset=0`;
- document status: `GET http://localhost:8000/api/v1/documents/{document_id}`;
- review resolution: `POST http://localhost:8000/api/v1/documents/{document_id}/review-resolution`;
- controlled reprocessing: `POST http://localhost:8000/api/v1/documents/{document_id}/reprocessing-requests`;
- OpenAPI document: `GET http://localhost:8000/openapi.json`;
- interactive API documentation: `http://localhost:8000/docs`.

### Backend Image

Build the shared API/worker image from the locked production dependencies:

```bash
docker build -t document-platform-api:dev .
docker run --rm --entrypoint id document-platform-api:dev
```

The runtime uses UID/GID `10001`, includes English Tesseract data and has a
writable `/app/data` directory. The default command starts the API; the image
also contains the worker module and Alembic migrations.

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
production authentication or deployment configuration.

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
is a manual local smoke test, not part of the default CI pipeline.

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

Run the operator console in a second terminal:

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

### Temporal Handoff Environment

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
extracts explicitly labelled fields, validates their completeness and persists
the decision. `AUTO_APPROVE` atomically transitions the document to `APPROVED`
and the run to `COMPLETED`; `REVIEW_REQUIRED` transitions both to review. The
console stops polling after either automated outcome. A configured local review
operator can then approve or reject the review-required document. Resolution is
atomic, immutable and idempotent for the same decision, reviewer and note.

### Local Failure Demonstration

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

Set these local-only values before resolving a review through the API or console:

```bash
export DOCUMENT_PLATFORM_REVIEW_OPERATOR_TOKEN='replace-with-at-least-32-characters'
export DOCUMENT_PLATFORM_REVIEW_OPERATOR_ID='local-reviewer'
```

The console sends the token only for the resolution request and never persists
it. This static bearer-token mechanism is a development fixture, not an
identity or authorization system.

Before starting an OCR-recommended workflow, install the `tesseract` executable
with the required language data and verify it with `tesseract --list-langs`.
The default configuration expects the `eng` language and exposes command,
language, raster DPI and per-page timeout through `.env`.

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

### Metrics

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

The versioned API contract is stored at
[`docs/contracts/document-platform.openapi.json`](docs/contracts/document-platform.openapi.json).
After changing an HTTP contract, regenerate the JSON and frontend types with:

```bash
uv run python scripts/export_openapi.py
cd apps/operator-console
pnpm generate:api
```

Backend tests detect runtime-to-JSON drift; `pnpm check:api` detects
JSON-to-TypeScript drift. Generated TypeScript is never edited manually.

PostgreSQL uses local-only credentials from `compose.yaml`. Copy `.env.example`
to `.env` only when overriding defaults. Alembic is the only schema owner;
application startup never creates or modifies tables.

Local document blobs are written below `data/` by default and are excluded from
Git. Override the root with `DOCUMENT_PLATFORM_STORAGE_ROOT` and the 20 MiB
upload limit with `DOCUMENT_PLATFORM_MAX_DOCUMENT_BYTES`. PDF inspection rejects
invalid, encrypted and over-limit files; the default page limit is 50 and can be
set through `DOCUMENT_PLATFORM_MAX_DOCUMENT_PAGES`.

Run the quality gates with:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

From a fresh checkout, run the locked backend/frontend checks, Compose
configuration validation and package SBOM exports together with:

```bash
bash scripts/verify_clean_checkout.sh
```

This requires Python 3.13, `uv`, Node.js 24, pnpm 11.23, `jq` and a running
Docker daemon for Testcontainers. It does not start the application stack or
run browser accessibility checks, Gitleaks or image scans; those remain
separate checks. One real OCR integration test is skipped if Tesseract is not
installed. Generated reports and SBOMs stay in ignored paths.

Run the frontend quality gates with:

```bash
cd apps/operator-console
pnpm check
```

The operator console also has a local Storybook catalogue for reusable visual
components. Run it with `pnpm storybook`; build the static catalogue with
`pnpm build-storybook`. The Storybook a11y addon is enabled for interactive
inspection. Component tests also run axe semantic checks. Browser-based
contrast and keyboard-flow verification remains separate; this project does
not claim formal WCAG conformance.

The review panel keeps native controls in a tested keyboard order. When a
review decision is rejected by the API, focus moves to the associated alert and
the operator-token field references that error message.

Run the browser accessibility checks locally with:

```bash
cd apps/operator-console
pnpm test:a11y:browser
```

The command starts Storybook when necessary, runs axe in Chromium against the
review outcome, and checks the narrow 320 px layout. It is intentionally not
part of the ordinary CI gate.

Tests enforce branch coverage of at least 85%. The same command writes a local
HTML report to `htmlcov/index.html` and a machine-readable report to
`coverage.xml`. CI retains both as the `backend-coverage` artifact for 14 days.

CI also exports the locked Python runtime dependencies as a CycloneDX 1.5 SBOM
in the `python-runtime-sbom` artifact. Generate the same file locally with:

```bash
mkdir -p artifacts
uv export --preview-features sbom-export --format cyclonedx1.5 --no-dev --locked --offline --quiet --output-file artifacts/python-runtime.cdx.json
```

The frontend job likewise exports production dependencies from
`apps/operator-console/pnpm-lock.yaml` as the `frontend-runtime-sbom` artifact.
Generate it locally from `apps/operator-console` with:

```bash
mkdir -p ../../artifacts
pnpm sbom --sbom-format cyclonedx --sbom-type application --lockfile-only --prod > ../../artifacts/frontend-runtime.cdx.json
```

The preview `uv` export and pnpm lockfile export are package inventories, not
vulnerability scans. They do not inventory OS packages or the final images;
the frontend export also excludes build-only dependencies.

For an optional inventory of freshly built local images, use Docker Scout:

```bash
docker build -t document-platform-api:sbom .
docker build -t document-platform-console:sbom apps/operator-console
mkdir -p artifacts
DOCKER_SCOUT_OFFLINE=true docker scout sbom --format cyclonedx --output artifacts/api-image.cdx.json local://document-platform-api:sbom
DOCKER_SCOUT_OFFLINE=true docker scout sbom --format cyclonedx --output artifacts/console-image.cdx.json local://document-platform-console:sbom
```

`local://` prevents a registry fallback, and Scout's offline mode avoids
outbound lookups during analysis. These scans are not part of default
CI, are not attached to published images, and do not replace the lockfile
inventories: bundled frontend JavaScript may not appear as separate packages
in an image scan. Rebuild before scanning to avoid inventorying an old tag.

Before a release, run advisory checks against both lockfiles:

```bash
uv audit --locked
cd apps/operator-console
pnpm audit
```

These require access to the advisory services and report only vulnerabilities
known at the time of the query. They do not replace a vulnerability scan of
freshly built images or a review of the exact release commit.

For a final-image vulnerability scan, rebuild with `--pull`, export the exact
images with `docker save`, then run Trivy against each archive. The scanner
database is cached under ignored `artifacts/trivy-cache/`:

```bash
mkdir -p artifacts/trivy-cache
docker build --pull -t document-platform-api:audit .
docker build --pull -t document-platform-console:audit apps/operator-console
docker save -o artifacts/api-audit.tar document-platform-api:audit
docker save -o artifacts/console-audit.tar document-platform-console:audit
docker run --rm -v "$PWD/artifacts:/artifacts" -v "$PWD/artifacts/trivy-cache:/root/.cache/trivy" aquasec/trivy:0.74.0 image --input /artifacts/api-audit.tar --scanners vuln --severity HIGH,CRITICAL --format json --output /artifacts/api-cves.json
docker run --rm -v "$PWD/artifacts:/artifacts" -v "$PWD/artifacts/trivy-cache:/root/.cache/trivy" aquasec/trivy:0.74.0 image --input /artifacts/console-audit.tar --scanners vuln --severity HIGH,CRITICAL --format json --output /artifacts/console-cves.json
```

Inspect each report's `Results[].Vulnerabilities`; a successful scanner exit
does not mean zero findings. These local reports are not part of CI. Remove the
large image archives after review.

CI scans the complete Git history for committed secrets with Gitleaks. Run the
same check locally with:

```bash
docker run --rm --volume "$PWD:/repo" ghcr.io/gitleaks/gitleaks:v8.30.1 git --redact=100 --no-banner /repo
```

This scan blocks CI after a push; it is not installed as a local pre-commit
hook.

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE).
