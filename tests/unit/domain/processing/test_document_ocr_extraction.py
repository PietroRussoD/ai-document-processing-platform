"""OCR extraction domain invariants tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from document_platform.domain.processing import (
    DocumentOcrExtraction,
    InvalidDocumentOcrExtraction,
    OcrExtractionMethod,
)

RUN_ID = UUID("83838383-8383-4383-8383-838383838383")
EXTRACTED_AT = datetime(2026, 9, 16, 9, 0, tzinfo=UTC)


def extraction(**overrides: object) -> DocumentOcrExtraction:
    values: dict[str, object] = {
        "processing_run_id": RUN_ID,
        "method": OcrExtractionMethod.TESSERACT,
        "text": "Invoice 42",
        "page_count": 1,
        "character_count": 10,
        "non_whitespace_character_count": 9,
        "extracted_at": EXTRACTED_AT,
    }
    values.update(overrides)
    return DocumentOcrExtraction(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"page_count": 0}, "page_count"),
        ({"character_count": 9}, "character_count"),
        ({"non_whitespace_character_count": 8}, "non_whitespace"),
    ],
)
def test_rejects_inconsistent_extraction_metadata(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(InvalidDocumentOcrExtraction, match=message):
        extraction(**overrides)
