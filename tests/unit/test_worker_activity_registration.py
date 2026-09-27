"""Worker assembly tests for optional advisory activities."""

from pathlib import Path
from typing import Any

import pytest

import document_platform.worker as worker_module
from document_platform.application.temporal_contracts import (
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

    monkeypatch.setattr(worker_module, "create_database", fake_create_database)
    monkeypatch.setattr(worker_module, "Client", FakeClient)
    monkeypatch.setattr(worker_module, "Worker", FakeWorker)

    await worker_module.run_worker(Settings(storage_root=tmp_path))

    activity_names = {activity.__temporal_activity_definition.name for activity in registered}
    assert PROPOSE_INVOICE_FIELDS_ACTIVITY in activity_names
    assert RECORD_INVOICE_PROPOSAL_FAILURE_ACTIVITY in activity_names
