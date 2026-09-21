"""Explicit local-only fault adapter for workflow recovery demonstrations."""

from document_platform.application.ports import ExtractedPdfText


class LocalFaultInjectingPdfTextExtractor:
    async def extract(self, content: bytes) -> ExtractedPdfText:
        del content
        raise RuntimeError("local fault injection: embedded text extraction")
