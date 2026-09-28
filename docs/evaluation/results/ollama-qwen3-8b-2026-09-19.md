# Qwen3 8B Local Benchmark - 2026-09-19

## Scope

This is an isolated local comparison against the synthetic
`invoice-extraction-v1` corpus. It is not a production-accuracy claim and does
not change the deterministic workflow policy.

## Environment

- Runtime: Ollama `0.34.2`
- Model reference: `qwen3:8b`
- Model digest: `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`
- Model format: Qwen3 8.2B, `Q4_K_M`
- Hardware: Apple M3 Pro, 18 GB unified memory
- Request configuration: structured JSON schema, `temperature: 0`, `think: false`
- Corpus: `invoice-extraction-v1`, schema version `1`, eight synthetic cases

## Result

The raw report is [ollama-qwen3-8b-2026-09-19.json](ollama-qwen3-8b-2026-09-19.json).

| Metric | Result |
| --- | ---: |
| Exact document matches | 4 / 8 (50.0%) |
| Invoice number exact match | 7 / 8 (87.5%) |
| Issue date exact match | 5 / 8 (62.5%) |
| Supplier exact match | 8 / 8 (100.0%) |
| Currency exact match | 6 / 8 (75.0%) |
| Total exact match | 6 / 8 (75.0%) |
| Completed requests | 8 / 8 |
| Total API-call latency | 26.898 s |
| Mean API-call latency | 3.362 s |
| P95 API-call latency | 5.017 s |

The model accepted invalid or unsupported fields and inferred values from a
non-invoice payment sentence. It also left one date in its original format.

## Decision

Keep the deterministic extraction policy as the implemented workflow baseline.
At this benchmark checkpoint, the local Ollama adapter was evaluation-only.
The later opt-in workflow integration stores separate advisory proposals under
[ADR 0003](../../decisions/0003-keep-local-models-advisory.md). This historical
result does not establish model accuracy or authorize automatic approval.
Replacing deterministic extraction would still require a broader corpus and
a measured policy gate.

## Reproduction

```bash
uv run python scripts/evaluate_ollama_invoice_extraction.py --model qwen3:8b --timeout-seconds 60
```
