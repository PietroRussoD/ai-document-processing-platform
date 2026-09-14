# AI Document Processing Platform

A local-first platform for extracting, validating, and reviewing structured
data from business documents.

## Status

The `v0.1` ingestion milestone is in progress. The API accepts bounded PDF
uploads through real validation, local blob storage and atomic PostgreSQL
registration. A read endpoint exposes the current document and processing-run
status. The first operator UI is not yet implemented.

## Technology Direction

- Python 3.13 and `uv`;
- FastAPI and PostgreSQL;
- Temporal for durable asynchronous workflows;
- PyMuPDF and Tesseract for text extraction and OCR;
- Ollama for optional local structured extraction;
- React and TypeScript for upload, processing and review workflows.

## Architecture

The backend follows pragmatic ports and adapters. Business rules and use cases
do not depend on FastAPI, SQLAlchemy, Temporal, Tesseract, Ollama or filesystem
types. Adapters implement those external boundaries.

```text
HTTP / React -> application use cases -> domain rules
                       |       |       |
                  PostgreSQL  storage  Temporal/OCR/AI
```

See [architecture documentation](docs/architecture.md) and
[architectural decisions](docs/decisions/).

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
    outbound/                   # PostgreSQL, storage, Temporal, OCR, AI, notifications
  workflows/                    # deterministic Temporal workflow definitions
  observability/                # logging, metrics and correlation support
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
uv run uvicorn document_platform.bootstrap:app --reload
```

The API is available at `http://localhost:8000`. Current endpoints:

- liveness: `GET http://localhost:8000/health/live`;
- document ingestion: `POST http://localhost:8000/api/v1/documents`;
- document status: `GET http://localhost:8000/api/v1/documents/{document_id}`;
- OpenAPI document: `GET http://localhost:8000/openapi.json`;
- interactive API documentation: `http://localhost:8000/docs`.

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
processing run. Internal storage paths are never exposed by the HTTP contract.

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
