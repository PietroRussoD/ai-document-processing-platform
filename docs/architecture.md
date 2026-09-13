# Architecture

## Purpose

The platform accepts synthetic business documents, processes them asynchronously
and presents validated results for review. It is designed as a local-first
system: a clean default run does not require cloud credentials or a paid AI
provider.

## Components

```mermaid
flowchart LR
    Console[React operator console] --> API[FastAPI HTTP adapter]
    API --> Application[Application use cases]
    Application --> Domain[Domain rules]
    Application --> PostgreSQL[(PostgreSQL)]
    Application --> Storage[Local filesystem]
    Application --> Temporal[Temporal]
    Temporal --> Worker[Workflow activities]
    Worker --> Text[PyMuPDF and Tesseract]
    Worker --> Model[Extraction provider port]
    Model --> Fake[Deterministic fake]
    Model --> Ollama[Local Ollama]
    Model -. optional .-> OpenAI[External provider]
```

PostgreSQL is authoritative for documents, processing runs, state transitions,
review decisions and user-facing projections. Temporal stores durable workflow
execution history. Filesystem storage owns document blobs and derived artifacts.
The model provider is never an authority for business state.

## Dependency Direction

```text
adapters -> application -> domain
```

The domain does not import framework, database, workflow, OCR, storage or model
SDK types. The application defines ports only for boundaries that are external,
fallible or plausibly replaceable: repositories, object storage, workflow start,
text extraction, structured extraction and notifications.

Temporal workflows are deterministic orchestration. Database, filesystem, OCR,
clock and model calls happen in Activities, never directly inside workflow code.

## Transaction Ownership

Application use cases own transaction boundaries through a unit of work.
Repositories use its shared session but never commit independently. A use case
must commit explicitly after all related writes succeed; leaving the context
without a commit, including after an exception, rolls the transaction back.
This allows document, processing-run, idempotency and workflow-start records to
be persisted atomically when those capabilities are introduced.

## Domain Lifecycles

Document status describes the business outcome of the submitted content:

```mermaid
stateDiagram-v2
    [*] --> UPLOADED
    UPLOADED --> PROCESSING
    PROCESSING --> APPROVED: automatic validation
    PROCESSING --> REVIEW_REQUIRED: uncertain result
    REVIEW_REQUIRED --> APPROVED: reviewer approves
    REVIEW_REQUIRED --> REJECTED: reviewer rejects
```

Processing-run status describes one durable technical execution. Failures and
retries belong here rather than in the document lifecycle:

```mermaid
stateDiagram-v2
    [*] --> QUEUED
    QUEUED --> RUNNING
    QUEUED --> CANCELLED
    RUNNING --> COMPLETED
    RUNNING --> WAITING_RETRY
    WAITING_RETRY --> RUNNING: retry
    RUNNING --> REVIEW_REQUIRED
    REVIEW_REQUIRED --> RUNNING: review resolved
    RUNNING --> FAILED
    RUNNING --> CANCELLED
    WAITING_RETRY --> CANCELLED
```

Individual processing stages will have their own persisted lifecycle when stage
execution is introduced; it is not simulated by the current domain model.

## Persistence Model

One document can have multiple processing runs, allowing an explicit future
reprocessing operation without overwriting execution history:

```mermaid
erDiagram
    DOCUMENTS ||--o{ PROCESSING_RUNS : has
    DOCUMENTS {
        uuid id PK
        string content_sha256
        string status
        int version
    }
    PROCESSING_RUNS {
        uuid id PK
        uuid document_id FK
        string status
        int attempt_count
        int version
    }
```

Deleting a document as part of an explicit retention operation cascades to its
processing runs. Ordinary processing never deletes either record.

## Repository Structure

The layout in the root README is intentionally a map, not a request to create
empty packages. A vertical slice creates only the directories it needs and
tests mirror the behavior level:

```text
tests/unit/          domain and application rules
tests/integration/   real adapters and infrastructure boundaries
tests/e2e/           API and browser journeys
```

## Current Boundaries

| Boundary | Default implementation | Optional implementation |
| --- | --- | --- |
| Object storage | Local filesystem | S3-compatible adapter |
| Structured extraction | Deterministic fake for CI | Ollama; policy-gated OpenAI comparison |
| Text extraction | PyMuPDF, Tesseract when required | None initially |
| Workflow execution | Temporal development server | Managed/self-hosted Temporal later |

## Related Decisions

- [ADR 0001: Pragmatic Ports and Adapters](decisions/0001-pragmatic-ports-and-adapters.md)
