# ADR 0008: Record safe terminal workflow failure evidence

## Status

Accepted

## Context

A Temporal activity can exhaust its bounded retry policy after an external or
technical failure. Temporal retains the execution history, but the platform's
authoritative operational state is PostgreSQL. Leaving a processing run marked
as `RUNNING`, or persisting an unbounded exception message, would make the
status projection misleading and could expose implementation details or
document-adjacent data.

Operators need to distinguish a completed business decision from a terminal
technical failure, know the failing stage, and create a controlled replacement
run without rewriting the failed evidence.

## Decision

When a workflow receives a terminal `ActivityError`, it invokes an explicit
recording activity before rethrowing the error to Temporal. The recording
transaction marks the processing run and document as `FAILED` and stores only:

- a bounded `ProcessingStage` enum;
- a bounded `ProcessingFailureCode` enum; and
- the terminal state timestamps already owned by the aggregates.

Raw exception messages, stack traces, provider responses, document text and
storage paths are not persisted in the business-state model or returned by the
status endpoint. The workflow is then still failed in Temporal; PostgreSQL does
not pretend that the workflow completed successfully.
The current-run status projection exposes only the bounded stage and code;
the console renders those values for an operator.

The initial mapping records `ACTIVITY_RETRY_EXHAUSTED`. The enums are designed
to allow future safe codes without changing the public failure-model shape.
An explicit local-only fault-injection setting can fail embedded-text
extraction for repeatable verification. It is rejected outside the `local`
environment and supports no production path.

Recovery remains the existing authenticated reprocessing operation: it creates
a distinct queued run referencing the failed source run. It does not restart or
mutate the failed run.

## Consequences

- PostgreSQL status queries reconcile with terminal Temporal activity failures.
- Operators can inspect a safe failure category and stage without raw error
  leakage.
- Failure history remains immutable and linked to any replacement run.
- The error is rethrown, preserving Temporal's execution semantics and history.
- The operator work queue consumes the bounded failure evidence directly from
  PostgreSQL rather than parsing logs; future notifications can use the same
  safe fields.
