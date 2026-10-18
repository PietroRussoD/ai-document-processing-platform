"""Worker assembly tests for optional advisory activities."""

from pathlib import Path
from typing import Any, NoReturn

import pytest

import document_platform.worker as worker_module
from document_platform.adapters.outbound.kubernetes import KubernetesParserRuntimeConnection
from document_platform.application.temporal_contracts import (
    EXTRACT_DOCUMENT_TEXT_ACTIVITY,
    EXTRACT_OCR_TEXT_ACTIVITY,
    PROPOSE_INVOICE_FIELDS_ACTIVITY,
    RECORD_INVOICE_PROPOSAL_FAILURE_ACTIVITY,
)
from document_platform.settings import Settings


@pytest.mark.anyio
async def test_registers_proposal_activity_without_calling_ollama(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    ca_file = tmp_path / "ca.pem"
    token_file = tmp_path / "token"
    ca_file.write_text("synthetic CA")
    token_file.write_text("synthetic token")
    registered: list[Any] = []

    class FakeDatabase:
        sessions = object()

        async def dispose(self) -> None:
            pass

    class FakeClient:
        @staticmethod
        async def connect(*args: object, **kwargs: object) -> object:
            return object()

    class FakeWorker:
        def __init__(self, *args: object, activities: list[Any], **kwargs: object) -> None:
            registered.extend(activities)

        async def run(self) -> None:
            pass

    def fake_create_database(settings: Settings) -> FakeDatabase:
        return FakeDatabase()

    def verify_parser_connection(connection: KubernetesParserRuntimeConnection) -> None:
        del connection

    monkeypatch.setattr(worker_module, "create_database", fake_create_database)
    monkeypatch.setattr(worker_module, "Client", FakeClient)
    monkeypatch.setattr(worker_module, "Worker", FakeWorker)
    monkeypatch.setattr(
        KubernetesParserRuntimeConnection,
        "verify_connection",
        verify_parser_connection,
    )

    await worker_module.run_worker(
        Settings(
            storage_root=tmp_path,
            parser_kubernetes_endpoint="https://127.0.0.1:6443",
            parser_kubernetes_namespace="pdf-parser",
            parser_kubernetes_ca_file=ca_file,
            parser_kubernetes_token_file=token_file,
            parser_job_image="document-platform-parser:dev",
        )
    )

    activity_names = {activity.__temporal_activity_definition.name for activity in registered}
    assert EXTRACT_DOCUMENT_TEXT_ACTIVITY in activity_names
    assert EXTRACT_OCR_TEXT_ACTIVITY in activity_names
    assert PROPOSE_INVOICE_FIELDS_ACTIVITY in activity_names
    assert RECORD_INVOICE_PROPOSAL_FAILURE_ACTIVITY in activity_names


@pytest.mark.anyio
async def test_worker_fails_closed_without_parser_runtime_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_database_starts(settings: Settings) -> NoReturn:
        del settings
        pytest.fail("database must not start before parser configuration")

    monkeypatch.setattr(
        worker_module,
        "create_database",
        fail_if_database_starts,
    )

    with pytest.raises(ValueError, match="isolated parser runtime configuration is required"):
        await worker_module.run_worker(Settings())
