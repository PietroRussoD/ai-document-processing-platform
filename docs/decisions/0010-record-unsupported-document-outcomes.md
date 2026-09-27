# ADR 0010: Record Unsupported Documents as a Terminal Outcome

## Status

Accepted.

## Context

The classifier recognizes invoices, purchase orders and credit notes, but only
invoice extraction is implemented. An unknown or recognized non-invoice
document previously completed its Temporal run while its document stayed in
`PROCESSING`, making completed work appear active indefinitely.

## Decision

Complete the processing run and transition its document to `UNSUPPORTED` in the
same database transaction when classification is not an invoice.
The persisted classification distinguishes an unknown document from a
recognized type whose structured extraction is not implemented. Expose the
outcome in a separate operator queue. Do not offer reprocessing until a new
supported processing capability can change the outcome.

The migration backfills documents whose latest completed run has a non-invoice
classification and whose document status is still `PROCESSING`.

## Consequences

- A successful workflow no longer leaves an unsupported document in an active
  state.
- Operators can distinguish unsupported input from technical failure and
  invoice review.
- Adding a document type later requires an explicit workflow capability and
  reprocessing policy; a classifier match alone does not imply support.
