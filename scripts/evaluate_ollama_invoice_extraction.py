"""Evaluate a local Ollama model against the versioned invoice corpus."""

import argparse
import json
from pathlib import Path

from document_platform.adapters.outbound.ollama import (
    OllamaInvoiceExtractionClient,
    OllamaInvoiceExtractionSettings,
)
from document_platform.evaluation import InvoiceExtractionEvaluator, load_invoice_extraction_corpus

CORPUS_PATH = Path(__file__).resolve().parents[1] / "docs/evaluation/invoice-extraction-v1.json"


def main() -> None:
    arguments = _parse_arguments()
    corpus = load_invoice_extraction_corpus(CORPUS_PATH)
    client = OllamaInvoiceExtractionClient(
        settings=OllamaInvoiceExtractionSettings(
            base_url=arguments.base_url,
            model=arguments.model,
            timeout_seconds=arguments.timeout_seconds,
        )
    )
    report = InvoiceExtractionEvaluator().evaluate(corpus=corpus, extractor=client.extract)
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate a local Ollama model against the invoice extraction corpus."
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Name of a model already available in Ollama.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:11434",
        help="Ollama API base URL. Defaults to %(default)s.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=60.0,
        help="Timeout for each model invocation. Defaults to %(default)s.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
