# ADR 0003: Keep Local Models Evaluation-Only Until a Policy Gate Is Met

## Status

Accepted.

## Context

The platform needs a zero-cost way to assess whether local structured extraction
can improve on deterministic labelled-field parsing. A local model is fallible,
has variable latency and can infer fields that are not supported by the product
policy. Wiring it directly into the Temporal worker would make model behavior a
source of persisted business state before its quality, cost and operational
limits are understood.

The initial synthetic benchmark of `qwen3:8b` produced four exact document
matches out of eight. It accepted unsupported or invalid values and inferred
fields from a non-invoice payment sentence.

## Decision

Keep the Ollama client outside the application workflow and use it only through
the versioned synthetic evaluation corpus. Calls use structured JSON output,
temperature zero, thinking disabled and an explicit local model reference.
Record model digest, hardware context, latency and exact-match results with
each comparison.

No model output is persisted, and no application port is introduced for model
extraction until a separately approved policy gate defines quality thresholds,
fallback behavior, timeout and retry ownership, data handling and user-review
semantics.

## Consequences

- Deterministic extraction remains the implemented workflow baseline.
- Model experiments cannot alter document, review or workflow state.
- Evaluation remains repeatable with synthetic data and has no cloud cost.
- A future integration must add an explicit vertical slice, operational
metrics and a broader corpus; it cannot be enabled as a configuration toggle.
