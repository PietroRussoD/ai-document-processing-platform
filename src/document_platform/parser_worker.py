"""Parse one bounded PDF from stdin and return one versioned JSON result."""

import argparse
import asyncio
import hashlib
import json
import sys

from document_platform.adapters.outbound.ocr import TesseractPdfOcrExtractor
from document_platform.adapters.outbound.pdf import PyMuPdfTextExtractor

_MAX_PAGES = 50
_MAX_TEXT_CHARACTERS = 1_000_000
_OCR_RASTER_DPI = 200
_OCR_MAX_PAGE_PIXELS = 20_000_000
_OCR_PAGE_TIMEOUT_SECONDS = 30.0
_TESSERACT_LANGUAGE = "eng"


def _positive_integer(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("value must be a positive integer") from None
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


async def process_pdf(
    operation: str,
    pdf: bytes,
    *,
    max_output_bytes: int,
) -> bytes | None:
    try:
        if operation == "embedded-text":
            extracted = await PyMuPdfTextExtractor(
                max_pages=_MAX_PAGES,
                max_characters=_MAX_TEXT_CHARACTERS,
            ).extract(pdf)
        elif operation == "ocr":
            extracted = await TesseractPdfOcrExtractor(
                command="tesseract",
                language=_TESSERACT_LANGUAGE,
                max_pages=_MAX_PAGES,
                max_characters=_MAX_TEXT_CHARACTERS,
                raster_dpi=_OCR_RASTER_DPI,
                max_page_pixels=_OCR_MAX_PAGE_PIXELS,
                page_timeout_seconds=_OCR_PAGE_TIMEOUT_SECONDS,
            ).extract(pdf)
        else:
            return None

        result: dict[str, str | int] = {
            "protocol_version": 1,
            "operation": operation,
            "input_sha256": hashlib.sha256(pdf).hexdigest(),
            "page_count": extracted.page_count,
            "text": extracted.text,
            "character_count": extracted.character_count,
            "non_whitespace_character_count": extracted.non_whitespace_character_count,
        }
        encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return encoded if len(encoded) <= max_output_bytes else None
    except Exception:
        # PDF and OCR exceptions can contain parser details or document content.
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", choices=("embedded-text", "ocr"), required=True)
    parser.add_argument("--max-input-bytes", type=_positive_integer, required=True)
    parser.add_argument("--max-output-bytes", type=_positive_integer, required=True)
    args = parser.parse_args()
    pdf = sys.stdin.buffer.read(args.max_input_bytes + 1)
    if not pdf or len(pdf) > args.max_input_bytes:
        return 7
    result = asyncio.run(process_pdf(args.operation, pdf, max_output_bytes=args.max_output_bytes))
    if result is None:
        return 7
    sys.stdout.buffer.write(result)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
