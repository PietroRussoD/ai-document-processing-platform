# ADR 0012: Use Temporal for Durable Document-Processing Orchestration

## Status

Accepted. Recorded retroactively on 2026-10-02. Temporal was introduced on
2026-09-15 and first released in `v0.2.0`. No comparison of alternatives was
recorded at that time; the alternatives below state the reasons that hold for
the implemented system.

## Context

Processing one document is an ordered pipeline: start the run, extract embedded
text, run OCR when needed, select the canonical text, classify, then either
extract, validate and apply an invoice decision or complete an unsupported
document. An optional advisory proposal runs after the deterministic outcome.

The steps call fallible local tools with very different costs. PyMuPDF
extraction is fast; Tesseract OCR runs serially with a per-page timeout; a
local model has variable latency and can be unavailable. A worker, the database
or a tool can fail between any two steps. Each step needs its own timeout and a
bounded retry budget, and an exhausted budget must leave a safe, visible
terminal state ([ADR 0008](0008-record-safe-terminal-workflow-failure-evidence.md)).

The workflow definition also changes while executions exist: the advisory
proposal stage was added after earlier versions had been released.

Without an orchestrator, the application would need its own per-run step-state
table, scheduling loop, retry and backoff rules, timeout detection, resumption
after a crash and a way to change the step sequence without breaking runs in
progress.

## Decision

- Temporal orchestrates one workflow execution per processing run:
  `ProcessBusinessDocumentWorkflow` on the `document-processing` task queue,
  with the deterministic workflow ID `process-business-document/{run_id}`.
- Temporal owns workflow execution history. PostgreSQL remains authoritative
  for business state and the status projection. The API and the operator
  console never query Temporal.
- Workflow code is deterministic orchestration only. Database, filesystem,
  OCR, clock and model calls happen in Activities.
- Every Activity is idempotent at processing-run level: its output is
  immutable, keyed by the run and reused on retry. Temporal does not provide
  this; the Activities do.
- Retry policies are bounded: at most three attempts for processing stages and
  failure recording; at most two attempts for the advisory proposal, 150
  seconds each and five minutes in total. Every stage has its own
  start-to-close timeout.
- The workflow is not started inside the upload transaction. The upload commits
  a workflow-start request with the document, and a separate dispatcher claims
  it with a lease and `SKIP LOCKED`, then starts the workflow with
  `REJECT_DUPLICATE` and `USE_EXISTING`. An already-started workflow counts as
  a successful handoff.
- Human review is outside the workflow. The workflow ends at
  `REVIEW_REQUIRED`; resolution is an API transaction
  ([ADR 0002](0002-preserve-operator-corrections-separately.md)). No workflow
  signals are used.
- Changes to the recorded command sequence use Temporal patches, such as
  `advisory-invoice-proposal-v1`, and are guarded by the replay test against
  synthetic `v0.9.0` histories.
- Locally, Temporal runs as `temporalio/auto-setup` with a dedicated PostgreSQL
  database and Temporal UI. A production deployment is not designed.

## Alternatives

- **A job queue such as Celery, RQ, Dramatiq or ARQ.** Not chosen. A job queue
  retries individual tasks but does not keep the durable state of a multi-step
  sequence. Chaining stages, recording which stage a run reached, resuming after
  a crash and handling terminal failure would become application tables and
  code. There is no equivalent of replay-tested workflow versioning.
- **A PostgreSQL state machine with polling workers**, the same pattern as the
  dispatcher. Feasible, with fewer moving parts. Not chosen because it would
  reimplement scheduling, per-stage timeouts, retries and resumption for every
  stage. The pattern is used only for the single handoff into Temporal.
- **Synchronous processing inside the upload request.** Not chosen. OCR can
  take minutes and model calls have variable latency, both beyond a reasonable
  request duration. A crash would lose the work, and API availability would
  depend on OCR and the model.
- **A batch DAG scheduler such as Airflow.** Not chosen. It is oriented to
  scheduled batch pipelines rather than one durable execution per uploaded
  document.
- **A managed cloud workflow service.** Not chosen. It would break the
  local-first, zero-cost default run and require cloud credentials.

## Consequences

- A run survives worker and process restarts. Completed Activities are not
  re-executed, and the workflow continues from the first incomplete stage.
- Timeouts and retries are declared per stage in the workflow, not scattered
  through Activity code.
- Temporal UI shows each execution's history, including Activity timings,
  attempts and failures. OCR and the advisory proposal are separate Activities,
  so their durations are already distinguishable. Distributed tracing is
  therefore not added here. The HTTP correlation identifier does not cross into
  the workflow ([ADR 0005](0005-use-bounded-http-correlation-identifiers.md));
  the processing run ID links a request to its workflow.
- An extra service and its database must be operated. Locally that is a
  Compose dependency; Temporal UI has no authentication.
- Contributors must follow the determinism rules. A change to the workflow
  command sequence requires a patch and a replay check, not only ordinary tests.
- An interrupted Activity is re-executed from the start. Idempotency remains the
  application's responsibility and must be preserved by every new Activity.
- Activities do not heartbeat. A worker that dies during a long Activity is
  detected only when its start-to-close timeout expires, up to five minutes for
  OCR.
- Business state and execution state can diverge. The failure-recording
  Activity exists so that a terminal workflow failure is reflected in
  PostgreSQL before the error is rethrown.
- The replay test proves workflow command-sequence compatibility only. It does
  not prove that Activity implementations or external integrations remain
  backward compatible.
- Production deployment, whether a managed service or a self-hosted cluster
  with authentication and TLS, remains undesigned.
