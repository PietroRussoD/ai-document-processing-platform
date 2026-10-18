"""Isolated parser command protocol tests."""

import hashlib
import json
from typing import Any, cast

import pymupdf
import pytest

from document_platform.parser_worker import process_pdf


def synthetic_pdf() -> bytes:
    document = cast(Any, pymupdf.open())
    page = document.new_page()
    page.insert_text((72, 72), "Synthetic parser fixture")
    return cast(bytes, document.tobytes())


@pytest.mark.anyio
async def test_embedded_text_result_is_bounded_and_binds_input_digest() -> None:
    pdf = synthetic_pdf()

    result = await process_pdf("embedded-text", pdf, max_output_bytes=10_000)

    assert result is not None
    payload = cast(dict[str, Any], json.loads(result))
    assert payload["protocol_version"] == 1
    assert payload["operation"] == "embedded-text"
    assert payload["input_sha256"] == hashlib.sha256(pdf).hexdigest()
    assert payload["page_count"] == 1
    assert payload["text"].strip() == "Synthetic parser fixture"
    assert payload["character_count"] == len(payload["text"])
    assert payload["non_whitespace_character_count"] == sum(
        not character.isspace() for character in payload["text"]
    )


@pytest.mark.anyio
async def test_rejects_invalid_pdf_without_returning_parser_details() -> None:
    result = await process_pdf("embedded-text", b"not a PDF", max_output_bytes=10_000)

    assert result is None


@pytest.mark.anyio
async def test_rejects_encoded_result_over_the_output_limit() -> None:
    result = await process_pdf("embedded-text", synthetic_pdf(), max_output_bytes=1)

    assert result is None
