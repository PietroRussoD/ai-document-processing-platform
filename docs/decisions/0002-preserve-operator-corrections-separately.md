# ADR 0002: Preserve Operator Corrections Separately from Extraction

## Status

Accepted.

## Context

Deterministic invoice extraction is an immutable technical result of one
processing run. A reviewer may need to approve an otherwise valid invoice by
correcting one or more missing or incorrect fields.

Overwriting the extraction would lose the original evidence, obscure why human
review was required and make a repeated resolution hard to distinguish from a
new business action. Storing an untyped edited JSON document would weaken field
validation and make status consumers infer audit semantics.

## Decision

Persist a non-empty, typed correction set separately from the original invoice
extraction and associate it with the immutable review resolution for that
processing run.

Before persistence, apply the corrections only in memory and validate the
effective invoice. Persist the review resolution and all correction rows in one
transaction. Do not allow corrections for a rejected decision. Replaying the
same decision, note and correction set returns the existing resolution; a
different set conflicts.

The status projection returns the original extraction and correction records.
The operator console derives effective reviewed values for presentation without
rewriting either persisted fact.

## Consequences

- Audit history distinguishes extracted values from human judgement.
- Existing extraction records retain their retry and provenance semantics.
- API and UI consumers must combine immutable values for an effective view.
- This is not a general document-editing or multi-version correction system.
- Changing an accepted correction requires a separate future business design;
  it cannot silently mutate the original resolution.
