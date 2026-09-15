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
    assert settings.storage_root == Path("data")
    assert settings.max_document_bytes == 20 * 1024 * 1024
    assert settings.max_document_pages == 50
    assert settings.database_url.scheme == "postgresql+asyncpg"
    assert settings.database_pool_size == 5
    assert settings.database_max_overflow == 5
    assert settings.database_pool_timeout_seconds == 5.0
    assert settings.temporal_target_host == "localhost:7233"
    assert settings.temporal_namespace == "default"
    assert settings.temporal_task_queue == "document-processing"
    assert settings.dispatcher_owner == "local-dispatcher"
    assert settings.dispatcher_batch_size == 10
    assert settings.dispatcher_lease_seconds == 30.0
    assert settings.dispatcher_poll_seconds == 2.0


def test_rejects_an_unknown_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCUMENT_PLATFORM_ENVIRONMENT", "staging")

    with pytest.raises(ValidationError):
        Settings()


def test_rejects_an_invalid_database_pool_size() -> None:
    with pytest.raises(ValidationError):
        Settings(database_pool_size=0)


def test_rejects_a_non_positive_document_size_limit() -> None:
    with pytest.raises(ValidationError):
        Settings(max_document_bytes=0)


def test_rejects_a_non_positive_document_page_limit() -> None:
    with pytest.raises(ValidationError):
        Settings(max_document_pages=0)


def test_rejects_an_invalid_dispatcher_batch_size() -> None:
    with pytest.raises(ValidationError):
        Settings(dispatcher_batch_size=0)


def test_rejects_an_invalid_dispatcher_poll_interval() -> None:
    with pytest.raises(ValidationError):
        Settings(dispatcher_poll_seconds=0)
