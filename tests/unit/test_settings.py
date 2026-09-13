"""Typed configuration tests."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from document_platform.settings import Settings


def test_uses_safe_local_defaults(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DOCUMENT_PLATFORM_ENVIRONMENT", raising=False)
    monkeypatch.delenv("DOCUMENT_PLATFORM_LOG_LEVEL", raising=False)

    settings = Settings()

    assert settings.environment == "local"
    assert settings.log_level == "INFO"


def test_rejects_an_unknown_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCUMENT_PLATFORM_ENVIRONMENT", "staging")

    with pytest.raises(ValidationError):
        Settings()
