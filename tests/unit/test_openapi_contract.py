"""Versioned OpenAPI contract tests."""

import json
from pathlib import Path
from typing import Any, cast

from document_platform.bootstrap import create_app
from document_platform.settings import Settings

CONTRACT_PATH = (
    Path(__file__).resolve().parents[2] / "docs/contracts/document-platform.openapi.json"
)


def test_versioned_openapi_matches_the_runtime_contract() -> None:
    versioned_contract = cast(
        dict[str, Any],
        json.loads(CONTRACT_PATH.read_text(encoding="utf-8")),
    )

    assert versioned_contract == create_app(Settings(environment="test")).openapi()
