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

Changes to expected values or cases require a new corpus version. Existing
versions remain immutable so comparisons remain reproducible.
