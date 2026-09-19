# Evaluation Corpus

`invoice-extraction-v1.json` is a small, versioned synthetic corpus for
structured invoice extraction. It contains no customer documents or production
data. Each case defines canonical text and the exact expected invoice fields.

The deterministic policy is evaluated against this corpus in the ordinary test
suite. A future Ollama adapter must use the same corpus and report per-field
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

The Ollama comparison is an isolated local experiment. It does not replace the
deterministic extraction policy, participate in Temporal workflows, or persist
model output. It sends the same corpus text to Ollama's structured-output API
and validates each response against an explicit JSON schema before evaluation.

After starting Ollama locally and making a model available, run:

```bash
uv run python scripts/evaluate_ollama_invoice_extraction.py --model <local-model>
```

The command intentionally requires an explicit model name. Record the model,
its version or digest, hardware context, and command output with any comparison
result; exact-match scores alone do not measure production extraction quality.

Changes to expected values or cases require a new corpus version. Existing
versions remain immutable so comparisons remain reproducible.
