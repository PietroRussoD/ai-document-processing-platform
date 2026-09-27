# ADR 0003: Keep Local Model Output Advisory

## Status

Accepted. Amended 2026-09-27 to allow a separate, immutable proposal while
keeping model output outside the authoritative processing result.

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
- Only a local Ollama provider is in scope. The selected text is bounded and
  transient; prompts, source text and raw model responses are not persisted or
  logged.
- The invoice workflow invokes the advisory activity only after deterministic
  completion and only in histories with the `advisory-invoice-proposal-v1`
  patch. The worker skips the model when disabled (the default). Provider
  failures use bounded Temporal retries and a separate durable outcome;
  operator visibility remains pending.
- The current benchmark is evidence for an advisory demo only, not a real-world
  accuracy claim. Any later move toward authoritative extraction requires a
  broader versioned corpus and measured policy gate.

## Consequences

- Existing deterministic processing remains unchanged and works without Ollama.
- The AI proposal can be compared with deterministic output without conflating
  their provenance or trust level.
- Provider outages do not turn a usable deterministic result into a failed
  document; the failure-recording activity writes a separate outcome after
  bounded retries.
- Provider timeout, unavailability and invalid response envelopes have separate
  safe error codes. A response body with invalid invoice JSON remains an
  `INVALID` proposal, not a provider outage. A separate immutable persistence
  contract now stores terminal provider failures without failing the document.
  The proposal and failure repositories serialize writes per run and reject
  opposite outcomes. Operator visibility remains pending.
- A public demo must disclose the local model, benchmark limitations and human
  review requirement.
