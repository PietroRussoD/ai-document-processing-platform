"""Embedded-text quality policy tests."""

import pytest

from document_platform.domain.processing import EmbeddedTextQuality, EmbeddedTextQualityPolicy


def test_recommends_ocr_below_the_configured_threshold() -> None:
    policy = EmbeddedTextQualityPolicy(minimum_non_whitespace_characters=100)

    assert policy.assess(non_whitespace_character_count=99) is EmbeddedTextQuality.OCR_RECOMMENDED


def test_accepts_text_at_the_configured_threshold() -> None:
    policy = EmbeddedTextQualityPolicy(minimum_non_whitespace_characters=100)

    assert policy.assess(non_whitespace_character_count=100) is EmbeddedTextQuality.SUFFICIENT


@pytest.mark.parametrize("value", [0, -1])
def test_rejects_an_invalid_threshold(value: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        EmbeddedTextQualityPolicy(value)
