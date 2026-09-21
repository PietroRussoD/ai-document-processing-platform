"""Local fault-injection adapter tests."""

import pytest

from document_platform.adapters.outbound.pdf import LocalFaultInjectingPdfTextExtractor


@pytest.mark.anyio
async def test_always_fails_without_inspecting_document_content() -> None:
    extractor = LocalFaultInjectingPdfTextExtractor()

    with pytest.raises(RuntimeError, match="local fault injection"):
        await extractor.extract(b"synthetic-document-content")
