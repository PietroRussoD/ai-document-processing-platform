# ADR 0001: Use Pragmatic Ports and Adapters

## Status

Accepted.

## Context

The platform needs to interact with PostgreSQL, local or S3-compatible storage,
Temporal, PDF/OCR tooling and structured-extraction providers. These boundaries
have different failure modes, data representations and replacement paths.

Making the domain depend directly on any of those libraries would make business
rules harder to test and would couple the product to a local implementation.
Creating interfaces around every class would add ceremony without an external
boundary to justify it.

## Decision

Use ports in the application layer only for real external boundaries:

- document and processing-run persistence;
- object storage;
- workflow start and signalling;
- embedded-text extraction and OCR;
- structured extraction providers;
- durable notification publishing.

FastAPI, SQLAlchemy, Temporal, Tesseract, Ollama and provider SDK objects are
mapped inside adapters. Domain and application tests use focused fakes where an
external dependency would obscure the behavior under test.

## Consequences

- Provider, storage and workflow changes remain localized at adapter boundaries.
- Tests can verify domain and application behavior without containers or a model.
- Mapping code is explicit and must be maintained when contracts change.
- No port is introduced until a vertical slice needs its boundary.
