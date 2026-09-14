"""Export the runtime FastAPI contract as deterministic JSON."""

import json
from pathlib import Path

from document_platform.bootstrap import create_app
from document_platform.settings import Settings

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "docs/contracts/document-platform.openapi.json"


def main() -> None:
    contract = create_app(Settings(environment="test")).openapi()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
