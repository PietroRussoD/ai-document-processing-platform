# AI Document Processing Platform

A local-first platform for extracting, validating, and reviewing structured
data from business documents.

## Status

The [`v0.4.0` tagged release](https://github.com/PietroRussoD/ai-document-processing-platform/tree/v0.4.0),
documented in the [release notes](docs/releases/v0.4.0.md), adds immutable
field-level invoice corrections to the authenticated review flow introduced in
`v0.3.0`. The worker performs bounded embedded-text extraction, a local OCR
fallback, canonical-text selection, deterministic document classification and
invoice validation. A complete invoice is automatically approved; an incomplete
one is handed off to review. The console derives a safe timeline from persisted
metadata and never renders extracted document text. The API accepts bounded PDF
uploads through real validation, local blob storage and atomic PostgreSQL
registration.
A read endpoint exposes the current document and processing-run status. The
operator console provides tested PDF selection and submission, including
acceptance identifiers, safe error feedback and polling of the persisted
document and processing-run status. Once available, the same status snapshot
also exposes safe extraction, selection, classification and review-resolution
metadata; it never returns extracted document text or blob paths.

`v0.4.0` lets an operator complete a missing or incorrect invoice extraction
without rewriting evidence. An immutable correction set is recorded beside the
original extraction and resolution. The status projection exposes both facts,
and the console derives effective reviewed values from them. The release also
adds a synthetic extraction corpus and a local Ollama comparison harness. The
recorded Qwen3 result does not meet the product policy, so model calls remain
evaluation-only and outside the document-processing workflow.

Current `v0.5.0` development is the operational-observability milestone. It
starts with low-cardinality Prometheus telemetry, then adds durable pipeline
backlog/outcome metrics, correlation-safe logs and an optional local
Prometheus/Grafana profile. Controlled reprocessing and the Operations Console
belong to the separate `v0.6.0` milestone. Notifications, retention, malware
scanning and production deployment remain separate decisions until their
concrete boundaries are designed and tested.

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
- notifications and retention workflows.

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

See [architecture documentation](docs/architecture.md) and
[architectural decisions](docs/decisions/). The repeatable release checks are
documented in the [v0.2 verification runbook](docs/runbooks/v0.2-verification.md).
The review-resolution flow is documented in the
[v0.3 verification runbook](docs/runbooks/v0.3-verification.md). Its `v0.4`
correction and local-model verification extension is documented separately in
the [v0.4 verification runbook](docs/runbooks/v0.4-verification.md).

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
- Prometheus metrics: `GET http://localhost:8000/metrics`;
- document ingestion: `POST http://localhost:8000/api/v1/documents`;
- document status: `GET http://localhost:8000/api/v1/documents/{document_id}`;
- review resolution: `POST http://localhost:8000/api/v1/documents/{document_id}/review-resolution`;
- OpenAPI document: `GET http://localhost:8000/openapi.json`;
- interactive API documentation: `http://localhost:8000/docs`.

Run the operator console in a second terminal:

```bash
cd apps/operator-console
pnpm install --frozen-lockfile
pnpm dev
```

Vite serves the console at `http://localhost:5173` and proxies `/api` requests
to the backend at `http://localhost:8000` by default. Override the development
target with `VITE_API_PROXY_TARGET` when required.

### Temporal Handoff Environment

The optional local Temporal profile is independent from the application
PostgreSQL instance. Start it when working on workflow handoff or inspecting
workflow execution history:

```bash
docker compose --profile temporal up -d
```

Temporal listens on `localhost:7233`; its local UI is available at
`http://localhost:8233`. The dispatcher is a separate process so HTTP uploads
remain available when Temporal is being restarted:

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
processing run. Its optional `processing_output` contains only extraction counts,
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

CI scans the complete Git history for committed secrets with Gitleaks. Run the
same check locally with:

```bash
docker run --rm --volume "$PWD:/repo" ghcr.io/gitleaks/gitleaks:v8.30.1 git --redact=100 --no-banner /repo
```

This scan blocks CI after a push; it is not installed as a local pre-commit
hook.

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE).
