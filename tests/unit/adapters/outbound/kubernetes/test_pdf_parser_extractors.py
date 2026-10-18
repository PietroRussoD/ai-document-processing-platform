"""Strict validation of parser Job responses."""

import asyncio
import hashlib
import json
from threading import Event

import pytest

from document_platform.adapters.outbound.kubernetes import (
    KubernetesPdfOcrExtractor,
    KubernetesPdfTextExtractor,
    ParserOperation,
)
from document_platform.application.ports import (
    OcrExtractionFailed,
    OcrTextLimitExceeded,
    ParserExecutionFailed,
    PdfPageLimitExceeded,
    PdfTextLimitExceeded,
)

_PDF = b"synthetic PDF bytes"


class FakeParserJobController:
    def __init__(self, response: bytes) -> None:
        self.response = response
        self.calls: list[tuple[ParserOperation, bytes]] = []

    def execute(
        self,
        operation: ParserOperation,
        pdf: bytes,
        *,
        cancel_event: Event | None = None,
    ) -> bytes:
        del cancel_event
        self.calls.append((operation, pdf))
        return self.response


class BlockingParserJobController(FakeParserJobController):
    def __init__(self, response: bytes) -> None:
        super().__init__(response)
        self.started = Event()
        self.cancelled = Event()

    def execute(
        self,
        operation: ParserOperation,
        pdf: bytes,
        *,
        cancel_event: Event | None = None,
    ) -> bytes:
        self.calls.append((operation, pdf))
        self.started.set()
        if cancel_event is not None:
            cancel_event.wait(timeout=2)
            if cancel_event.is_set():
                self.cancelled.set()
        return self.response


def _response(
    *,
    operation: ParserOperation = ParserOperation.EMBEDDED_TEXT,
    content: bytes = _PDF,
    text: str = "Invoice 123",
    **overrides: object,
) -> bytes:
    result: dict[str, object] = {
        "protocol_version": 1,
        "operation": operation.value,
        "input_sha256": hashlib.sha256(content).hexdigest(),
        "page_count": 1,
        "text": text,
        "character_count": len(text),
        "non_whitespace_character_count": sum(not character.isspace() for character in text),
    }
    result.update(overrides)
    return json.dumps(result).encode()


@pytest.mark.anyio
async def test_embedded_text_extractor_validates_and_returns_bounded_result() -> None:
    controller = FakeParserJobController(_response())
    extractor = KubernetesPdfTextExtractor(
        controller=controller,
        max_pages=5,
        max_characters=100,
    )

    result = await extractor.extract(_PDF)

    assert result.text == "Invoice 123"
    assert result.page_count == 1
    assert result.character_count == 11
    assert result.non_whitespace_character_count == 10
    assert controller.calls == [(ParserOperation.EMBEDDED_TEXT, _PDF)]


@pytest.mark.anyio
async def test_ocr_extractor_uses_ocr_operation() -> None:
    controller = FakeParserJobController(
        _response(operation=ParserOperation.OCR, text="OCR result")
    )
    extractor = KubernetesPdfOcrExtractor(
        controller=controller,
        max_pages=5,
        max_characters=100,
    )

    result = await extractor.extract(_PDF)

    assert result.text == "OCR result"
    assert controller.calls == [(ParserOperation.OCR, _PDF)]


@pytest.mark.anyio
async def test_activity_cancellation_reaches_controller_thread() -> None:
    controller = BlockingParserJobController(_response())
    extractor = KubernetesPdfTextExtractor(
        controller=controller,
        max_pages=5,
        max_characters=100,
    )
    task = asyncio.create_task(extractor.extract(_PDF))

    assert await asyncio.to_thread(controller.started.wait, 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert await asyncio.to_thread(controller.cancelled.wait, 1)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response",
    [
        b"not JSON",
        _response(protocol_version=True),
        _response(input_sha256="0" * 64),
        _response(operation=ParserOperation.OCR),
        _response(character_count=999),
        _response(non_whitespace_character_count=999),
        _response(extra="unexpected"),
        (
            b'{"protocol_version":1,"protocol_version":1,"operation":"embedded-text",'
            b'"input_sha256":"'
            + hashlib.sha256(_PDF).hexdigest().encode()
            + b'","page_count":1,"text":"Invoice 123","character_count":11,'
            b'"non_whitespace_character_count":10}'
        ),
    ],
)
async def test_embedded_text_extractor_rejects_invalid_result_envelopes(
    response: bytes,
) -> None:
    extractor = KubernetesPdfTextExtractor(
        controller=FakeParserJobController(response),
        max_pages=5,
        max_characters=100,
    )

    with pytest.raises(ParserExecutionFailed):
        await extractor.extract(_PDF)


@pytest.mark.anyio
async def test_extractors_enforce_page_and_character_limits() -> None:
    text_extractor = KubernetesPdfTextExtractor(
        controller=FakeParserJobController(_response(page_count=6)),
        max_pages=5,
        max_characters=100,
    )
    ocr_extractor = KubernetesPdfOcrExtractor(
        controller=FakeParserJobController(_response(operation=ParserOperation.OCR, page_count=6)),
        max_pages=5,
        max_characters=100,
    )
    limited_text_extractor = KubernetesPdfTextExtractor(
        controller=FakeParserJobController(_response(text="too long")),
        max_pages=5,
        max_characters=3,
    )
    limited_ocr_extractor = KubernetesPdfOcrExtractor(
        controller=FakeParserJobController(
            _response(operation=ParserOperation.OCR, text="too long")
        ),
        max_pages=5,
        max_characters=3,
    )

    with pytest.raises(PdfPageLimitExceeded):
        await text_extractor.extract(_PDF)
    with pytest.raises(OcrExtractionFailed, match="page count"):
        await ocr_extractor.extract(_PDF)
    with pytest.raises(PdfTextLimitExceeded):
        await limited_text_extractor.extract(_PDF)
    with pytest.raises(OcrTextLimitExceeded):
        await limited_ocr_extractor.extract(_PDF)
