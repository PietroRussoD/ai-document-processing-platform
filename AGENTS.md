# Repository Guidance

## Scope

Build the AI Document Processing Platform incrementally. Each change must add a
small, observable behavior with focused tests and documentation that describes
only implemented behavior.

## Conventions

- Keep source code, comments, tests, API contracts, commits and repository
  documentation in English.
- Prefer explicit domain and application code over framework-specific shortcuts.
- Keep external boundaries behind focused ports only when they are genuinely
  replaceable or fallible.
- Do not log document contents, prompts, credentials, tokens or signed URLs.
- Use synthetic fixtures only.
- Run the narrowest relevant verification command before proposing a commit.

## Architecture and Layout

The intended repository layout is documented in `README.md` and
`docs/architecture.md`. Keep dependencies directed inward:

```text
adapters -> application -> domain
```

- `domain` contains no framework or infrastructure imports.
- `application` owns use cases and ports; it has no FastAPI, SQLAlchemy,
  Temporal, OCR, model-provider or storage SDK types in public contracts.
- `adapters` map transport/persistence/provider representations at their edge.
- `workflows` contain deterministic Temporal orchestration only; I/O occurs in
  Activities implemented through application ports.
- `apps/operator-console` owns browser code and consumes generated OpenAPI
  contracts rather than backend internals.

Create a package only when a vertical slice gives it a concrete responsibility.
Do not add empty layers, generic base classes or an interface for every class.

## Default Verification

```text
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```
