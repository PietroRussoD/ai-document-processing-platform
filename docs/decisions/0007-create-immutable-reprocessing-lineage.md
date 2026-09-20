# ADR 0007: Create immutable processing-run lineage for controlled reprocessing

## Status

Accepted

## Context

A document can reach a terminal technical run after a worker or integration
failure, or a business terminal state after automated validation or review.
An operator needs a controlled way to run the same immutable source document
again after investigating a failure or changing an explicitly versioned
processing configuration.

Restarting the old run would rewrite timestamps, attempts and processing
outputs. Accepting a second upload would duplicate the document identity and
lose the operational link between cause and recovery. Allowing a request while
another run is active would create competing workflow executions and ambiguous
status projections.

## Decision

`v0.6` introduces an authenticated, explicit reprocessing operation. It is
allowed only when the current processing run is terminal (`COMPLETED`, `FAILED`
or `CANCELLED`). A document in `REVIEW_REQUIRED` must use the existing review
workflow; it cannot be bypassed by reprocessing.

The operation atomically creates:

- a new `QUEUED` processing run that references the source run as its
  predecessor;
- a durable reprocessing audit record containing the bounded operator identity,
  reason, request time, source-run ID and replacement-run ID;
- a workflow-start request for the replacement run.

The original blob is reused. Extraction, validation, review and correction
records remain attached to their original run and are never copied or mutated.
The replacement run produces its own immutable output. For an `APPROVED` or
`REJECTED` document, the document lifecycle explicitly returns to
`PROCESSING`; a failed or cancelled run on an already-processing document does
not require a redundant document transition.

Every request carries a bounded idempotency key scoped to the document and its
request payload. A replay with the same key and equivalent request returns the
existing operation; a different payload conflicts. The transaction locks the
document and source run, and PostgreSQL enforces at most one active run per
document with a partial unique index over `QUEUED`, `RUNNING`, `WAITING_RETRY`
and `REVIEW_REQUIRED` statuses.

The existing local bearer-token boundary is reused for this privileged demo
operation. It is not represented as production identity or authorization.

## Consequences

- Recovery history is queryable without rewriting technical or review evidence.
- A crash after commit is recoverable through the existing workflow-start
  dispatcher boundary.
- The status projection can expose the current run and bounded lineage metadata
  without returning document text or internal paths.
- A reprocessing action cannot repair an active run or replace a human review
  decision; those remain separate operations.
- The partial unique index is the final concurrency guard even if multiple API
  instances process requests concurrently.
