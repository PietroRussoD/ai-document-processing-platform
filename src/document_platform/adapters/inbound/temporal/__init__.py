"""Temporal activity adapters."""

from document_platform.adapters.inbound.temporal.extract_document_text_activity import (
    ExtractDocumentTextActivity,
)
from document_platform.adapters.inbound.temporal.extract_ocr_text_activity import (
    ExtractOcrTextActivity,
)
from document_platform.adapters.inbound.temporal.select_processing_text_activity import (
    SelectProcessingTextActivity,
)
from document_platform.adapters.inbound.temporal.start_processing_run_activity import (
    StartProcessingRunActivity,
)

__all__ = [
    "ExtractDocumentTextActivity",
    "ExtractOcrTextActivity",
    "SelectProcessingTextActivity",
    "StartProcessingRunActivity",
]
