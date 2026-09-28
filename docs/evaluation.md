# Evaluation Corpus

`invoice-extraction-v1.json` is a small, versioned synthetic corpus for
structured invoice extraction. It contains no customer documents or production
data. Each case defines canonical text and the exact expected invoice fields.

The deterministic policy is evaluated against this corpus in the ordinary test
suite. The local Ollama comparison uses the same corpus and reports per-field
exact matches separately from operational metrics such as latency and failure
rate. A result from this corpus is not a claim of real-world model accuracy.

Run the deterministic baseline locally with:

```bash
uv run python scripts/evaluate_invoice_extraction.py
```

The JSON report includes exact document matches, per-field exact-match rates
and the individual mismatches. It is intentionally deterministic and contains
no timestamps, so reports can be diffed between implementations.

## Local Ollama spike

The Ollama comparison command is an isolated local experiment. It does not
replace deterministic extraction or persist its comparison output.
The comparison sends the same corpus text to Ollama's structured-output API
and validates each response against an explicit JSON schema before evaluation.

Separately, the opt-in invoice workflow persists an advisory proposal after
deterministic completion. The status API exposes proposed fields, typed issues
and model provenance in `current_run.ai_proposal`, or a terminal provider
failure in `current_run.ai_proposal_failure`. The console compares proposals
with deterministic values, supports explicit field adoption and records
correction provenance after operator approval. See
[ADR 0003](decisions/0003-keep-local-models-advisory.md) and the
[v1.0 demo verification](runbooks/v1.0-verification.md).

The console supports evaluation of an individual document during review.
Corpus-wide exact-match and latency reports remain CLI outputs; there is no
aggregate evaluation dashboard.

After starting Ollama locally and making a model available, run:

```bash
uv run python scripts/evaluate_ollama_invoice_extraction.py --model <local-model>
```

The command intentionally requires an explicit model name. Record the model,
its version or digest, hardware context, and command output with any comparison
result; exact-match scores alone do not measure production extraction quality.
Its JSON output also records request latency measured around each local API call
and the number of failed requests. Requests set `think: false` to keep the
structured extraction comparison bounded.

The first recorded local comparison is
[Qwen3 8B on 2026-09-19](evaluation/results/ollama-qwen3-8b-2026-09-19.md).

Changes to expected values or cases require a new corpus version. Existing
versions remain immutable so comparisons remain reproducible.
