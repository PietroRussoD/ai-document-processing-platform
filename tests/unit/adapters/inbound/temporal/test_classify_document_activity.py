"""Temporal document-classification activity tests."""

from uuid import UUID

import pytest

from document_platform.adapters.inbound.temporal import ClassifyDocumentActivity
from document_platform.application.commands import ClassifyDocument, DocumentClassified

RUN_ID = UUID("a2a2a2a2-a2a2-42a2-82a2-a2a2a2a2a2a2")


class RecordingClassifyDocument:
    def __init__(self) -> None:
        self.commands: list[ClassifyDocument] = []

    async def __call__(self, command: ClassifyDocument) -> DocumentClassified:
        self.commands.append(command)
        return DocumentClassified(command.processing_run_id, replayed=False)


@pytest.mark.anyio
async def test_maps_the_temporal_argument_to_the_application_command() -> None:
    handler = RecordingClassifyDocument()
    activity = ClassifyDocumentActivity(handler)  # type: ignore[arg-type]

    await activity.classify_document(str(RUN_ID))

    assert handler.commands == [ClassifyDocument(RUN_ID)]
