# Demo Documents

These three PDFs are generated from synthetic content by
[`scripts/generate_demo_documents.py`](../../scripts/generate_demo_documents.py).
They contain no real people, companies, or transactions. Regenerate them with:

```bash
uv run python scripts/generate_demo_documents.py
```

Upload them one at a time in the local console at `http://localhost:8088`:

| File | Text path | Expected classification | Expected outcome |
| --- | --- | --- | --- |
| `invoice-digital.pdf` | Embedded PDF text | `INVOICE` | `REVIEW_REQUIRED` |
| `invoice-scanned.pdf` | Tesseract OCR | `INVOICE` | `REVIEW_REQUIRED` |
| `equipment-report.pdf` | Embedded PDF text | `UNKNOWN` (`NO_MATCH`) | `UNSUPPORTED` |

The digital invoice uses CAD, which the deterministic extractor deliberately
does not support. With Ollama enabled, its advisory proposal can suggest the
currency and amount; the operator must still select and approve the values.
Without Ollama, they can be entered manually. The scanned invoice omits its
issue date and therefore requires operator review after OCR. The scanned example
needs the configured English Tesseract data. These files demonstrate the
processing workflow, not an AI model's accuracy.
