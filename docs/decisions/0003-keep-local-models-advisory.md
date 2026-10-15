# ADR 0003: Keep Local Model Output Advisory

## Status

Accepted. Amended 2026-09-27 for immutable workflow proposals, 2026-09-28 for
API/console visibility and explicit operator adoption, and 2026-10-14 to clarify
text persistence and the recorded advisory execution state.

## Context

The platform needs a zero-cost way to demonstrate and assess local structured
extraction. A local model is fallible, has variable latency and can infer fields
that are not supported by source text or product policy. The recorded Qwen3 8B
benchmark produced four exact document matches out of eight and inferred a
value from a non-invoice payment sentence. Model output is not reliable enough
to replace deterministic extraction or to approve a document automatically.

## Decision

- Deterministic extraction, validation and human review remain authoritative.
- A local model may produce a separate immutable invoice proposal with model,
  prompt and selected-text-hash provenance. It must not overwrite or modify the
  deterministic extraction or review decision.
- Model output is advisory and always requires human review. No confidence
  score or model status can automatically approve an invoice.
- Only a local Ollama provider is in scope. PDF and OCR extraction results,
  including their text, are persisted for reuse by processing stages. The model
  call uses bounded selected text without persisting an additional copy, its
  assembled prompt or the raw model response. Document text, prompts and raw
  responses are not logged.
- The invoice workflow invokes the advisory activity only after deterministic
  completion and only in histories with the `advisory-invoice-proposal-v1`
  patch. The worker skips the model when disabled (the default). Provider
  failures use bounded Temporal retries and a separate durable outcome.
  The status API and console expose proposals and terminal provider failures
  separately from deterministic processing output.
- The current benchmark is evidence for an advisory demo only, not a real-world
  accuracy claim. Any later move toward authoritative extraction requires a
  broader versioned corpus and measured policy gate.

## Consequences

- Existing deterministic processing remains unchanged and works without Ollama.
- The AI proposal can be compared with deterministic output without conflating
  their provenance or trust level.
- An operator may explicitly copy a proposal field into an approval correction.
  The correction stores `MANUAL` or `AI_PROPOSAL` provenance, and the API checks
  AI-sourced values against the persisted proposal. The operator remains the
  decision-maker; selecting a proposal never approves a document automatically.
- Provider outages do not turn a usable deterministic result into a failed
  document; the failure-recording activity writes a separate outcome after
  bounded retries.
- Provider timeout, unavailability and invalid response envelopes have separate
  safe error codes. A response body with invalid invoice JSON remains an
  `INVALID` proposal, not a provider outage. A separate immutable persistence
  contract now stores terminal provider failures without failing the document.
  The proposal and failure repositories serialize writes per run and reject
  opposite outcomes. A separate execution record distinguishes `DISABLED`,
  `RUNNING`, `COMPLETED` and `FAILED`. A missing record remains unknown for
  historical runs or activities that have not recorded entry; it must not be
  interpreted as disabled. The console uses bounded polling and supports manual
  refresh, as described in the
  [execution contract](../architecture.md#advisory-execution-contract).
- A public demo must disclose the local model, benchmark limitations and human
  review requirement.
