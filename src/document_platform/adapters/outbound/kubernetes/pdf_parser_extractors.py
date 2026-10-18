"""Validate parser Job responses as embedded-text and OCR extractors."""

import hashlib
import json
from typing import Protocol, cast

import anyio

from document_platform.adapters.outbound.kubernetes.parser_job_controller import (
    ParserOperation,
)
from document_platform.application.ports import (
    ExtractedOcrText,
    ExtractedPdfText,
    OcrExtractionFailed,
    OcrTextLimitExceeded,
    ParserExecutionFailed,
    PdfPageLimitExceeded,
    PdfTextLimitExceeded,
)

_RESULT_FIELDS = {
    "protocol_version",
    "operation",
    "input_sha256",
    "page_count",
    "text",
    "character_count",
    "non_whitespace_character_count",
}


class _ParserJobExecutor(Protocol):
    def execute(self, operation: ParserOperation, pdf: bytes) -> bytes: ...


class _KubernetesPdfExtractor:
    def __init__(
        self,
        *,
        controller: _ParserJobExecutor,
        operation: ParserOperation,
        max_pages: int,
        max_characters: int,
    ) -> None:
        if max_pages <= 0:
            raise ValueError("max_pages must be positive")
        if max_characters <= 0:
            raise ValueError("max_characters must be positive")
        self._controller = controller
        self._operation = operation
        self._max_pages = max_pages
        self._max_characters = max_characters

    async def _extract(self, content: bytes) -> tuple[str, int, int, int]:
        response = await anyio.to_thread.run_sync(
            self._controller.execute,
            self._operation,
            content,
        )
        result = _decode_result(response, self._operation, content)
        if result[1] > self._max_pages:
            self._raise_page_limit()
        if result[2] > self._max_characters:
            self._raise_text_limit()
        return result

    def _raise_page_limit(self) -> None:
        raise NotImplementedError

    def _raise_text_limit(self) -> None:
        raise NotImplementedError


class KubernetesPdfTextExtractor(_KubernetesPdfExtractor):
    """Extract embedded text in a short-lived Kubernetes Job."""

    def __init__(
        self,
        *,
        controller: _ParserJobExecutor,
        max_pages: int,
        max_characters: int,
    ) -> None:
        super().__init__(
            controller=controller,
            operation=ParserOperation.EMBEDDED_TEXT,
            max_pages=max_pages,
            max_characters=max_characters,
        )

    async def extract(self, content: bytes) -> ExtractedPdfText:
        text, page_count, character_count, non_whitespace_character_count = await super()._extract(
            content
        )
        return ExtractedPdfText(
            text=text,
            page_count=page_count,
            character_count=character_count,
            non_whitespace_character_count=non_whitespace_character_count,
        )

    def _raise_page_limit(self) -> None:
        raise PdfPageLimitExceeded(self._max_pages)

    def _raise_text_limit(self) -> None:
        raise PdfTextLimitExceeded(self._max_characters)


class KubernetesPdfOcrExtractor(_KubernetesPdfExtractor):
    """Rasterize and OCR a PDF in a short-lived Kubernetes Job."""

    def __init__(
        self,
        *,
        controller: _ParserJobExecutor,
        max_pages: int,
        max_characters: int,
    ) -> None:
        super().__init__(
            controller=controller,
            operation=ParserOperation.OCR,
            max_pages=max_pages,
            max_characters=max_characters,
        )

    async def extract(self, content: bytes) -> ExtractedOcrText:
        text, page_count, character_count, non_whitespace_character_count = await super()._extract(
            content
        )
        return ExtractedOcrText(
            text=text,
            page_count=page_count,
            character_count=character_count,
            non_whitespace_character_count=non_whitespace_character_count,
        )

    def _raise_page_limit(self) -> None:
        raise OcrExtractionFailed("PDF page count is outside the supported limit")

    def _raise_text_limit(self) -> None:
        raise OcrTextLimitExceeded(self._max_characters)


def _decode_result(
    response: bytes,
    operation: ParserOperation,
    content: bytes,
) -> tuple[str, int, int, int]:
    try:
        parsed: object = json.loads(
            response.decode("utf-8"), object_pairs_hook=_reject_duplicate_fields
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise ParserExecutionFailed("Parser returned an invalid result envelope") from None

    if not isinstance(parsed, dict):
        raise ParserExecutionFailed("Parser returned an unexpected result schema")
    result = cast(dict[str, object], parsed)
    if set(result) != _RESULT_FIELDS:
        raise ParserExecutionFailed("Parser returned an unexpected result schema")
    if type(result["protocol_version"]) is not int or result["protocol_version"] != 1:
        raise ParserExecutionFailed("Parser returned an unsupported protocol version")
    if result["operation"] != operation.value:
        raise ParserExecutionFailed("Parser result operation did not match the request")
    if result["input_sha256"] != hashlib.sha256(content).hexdigest():
        raise ParserExecutionFailed("Parser result digest did not match the input")

    text_value = result["text"]
    page_count_value = result["page_count"]
    character_count_value = result["character_count"]
    non_whitespace_count_value = result["non_whitespace_character_count"]
    if not isinstance(text_value, str):
        raise ParserExecutionFailed("Parser result text was not a string")
    if type(page_count_value) is not int or page_count_value <= 0:
        raise ParserExecutionFailed("Parser result page count was invalid")
    if type(character_count_value) is not int or character_count_value < 0:
        raise ParserExecutionFailed("Parser result character count was invalid")
    if type(non_whitespace_count_value) is not int or non_whitespace_count_value < 0:
        raise ParserExecutionFailed("Parser result non-whitespace count was invalid")

    character_count = len(text_value)
    non_whitespace_count = sum(not character.isspace() for character in text_value)
    if character_count_value != character_count:
        raise ParserExecutionFailed("Parser result character count did not match its text")
    if non_whitespace_count_value != non_whitespace_count:
        raise ParserExecutionFailed("Parser result non-whitespace count did not match its text")

    return (
        text_value,
        page_count_value,
        character_count_value,
        non_whitespace_count_value,
    )


def _reject_duplicate_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate result field")
        result[key] = value
    return result
