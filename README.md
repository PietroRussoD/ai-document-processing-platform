# AI Document Processing Platform

A local-first platform for extracting, validating, and reviewing structured
data from business documents.

## Status

Repository foundation. The first functional vertical slice is not implemented
yet. The architectural boundaries are recorded before framework code is added
so that later infrastructure does not determine the domain model.

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
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE).
