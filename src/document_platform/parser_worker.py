"""Parse one bounded PDF from stdin and return one versioned JSON result."""

import argparse
import asyncio
import hashlib
import json
import math
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
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def _positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("value must be a positive number") from None
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive number")
    return parsed


async def process_pdf(
    operation: str,
    pdf: bytes,
    *,
    max_output_bytes: int,
    max_pages: int = _MAX_PAGES,
    max_characters: int = _MAX_TEXT_CHARACTERS,
    tesseract_language: str = _TESSERACT_LANGUAGE,
    tesseract_raster_dpi: int = _OCR_RASTER_DPI,
    tesseract_max_page_pixels: int = _OCR_MAX_PAGE_PIXELS,
    tesseract_page_timeout_seconds: float = _OCR_PAGE_TIMEOUT_SECONDS,
) -> bytes | None:
    try:
        if operation == "embedded-text":
            extracted = await PyMuPdfTextExtractor(
                max_pages=max_pages,
                max_characters=max_characters,
            ).extract(pdf)
        elif operation == "ocr":
            extracted = await TesseractPdfOcrExtractor(
                command="tesseract",
                language=tesseract_language,
                max_pages=max_pages,
                max_characters=max_characters,
                raster_dpi=tesseract_raster_dpi,
                max_page_pixels=tesseract_max_page_pixels,
                page_timeout_seconds=tesseract_page_timeout_seconds,
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
    parser.add_argument("--max-pages", type=_positive_integer, default=_MAX_PAGES)
    parser.add_argument("--max-characters", type=_positive_integer, default=_MAX_TEXT_CHARACTERS)
    parser.add_argument("--tesseract-language", default=_TESSERACT_LANGUAGE)
    parser.add_argument(
        "--tesseract-raster-dpi",
        type=_positive_integer,
        default=_OCR_RASTER_DPI,
    )
    parser.add_argument(
        "--tesseract-max-page-pixels",
        type=_positive_integer,
        default=_OCR_MAX_PAGE_PIXELS,
    )
    parser.add_argument(
        "--tesseract-page-timeout-seconds",
        type=_positive_float,
        default=_OCR_PAGE_TIMEOUT_SECONDS,
    )
    args = parser.parse_args()
    pdf = sys.stdin.buffer.read(args.max_input_bytes + 1)
    if not pdf or len(pdf) > args.max_input_bytes:
        return 7
    result = asyncio.run(
        process_pdf(
            args.operation,
            pdf,
            max_output_bytes=args.max_output_bytes,
            max_pages=args.max_pages,
            max_characters=args.max_characters,
            tesseract_language=args.tesseract_language,
            tesseract_raster_dpi=args.tesseract_raster_dpi,
            tesseract_max_page_pixels=args.tesseract_max_page_pixels,
            tesseract_page_timeout_seconds=args.tesseract_page_timeout_seconds,
        )
    )
    if result is None:
        return 7
    sys.stdout.buffer.write(result)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
