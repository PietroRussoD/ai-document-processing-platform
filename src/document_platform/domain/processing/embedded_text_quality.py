"""Deterministic policy for deciding whether a PDF needs OCR."""

from dataclasses import dataclass
from enum import StrEnum


class EmbeddedTextQuality(StrEnum):
    SUFFICIENT = "SUFFICIENT"
    OCR_RECOMMENDED = "OCR_RECOMMENDED"


@dataclass(frozen=True, slots=True)
class EmbeddedTextQualityPolicy:
    minimum_non_whitespace_characters: int

    def __post_init__(self) -> None:
        if self.minimum_non_whitespace_characters < 1:
            raise ValueError("minimum_non_whitespace_characters must be positive")

    def assess(self, *, non_whitespace_character_count: int) -> EmbeddedTextQuality:
        if non_whitespace_character_count < 0:
            raise ValueError("non_whitespace_character_count must not be negative")
        if non_whitespace_character_count < self.minimum_non_whitespace_characters:
            return EmbeddedTextQuality.OCR_RECOMMENDED
        return EmbeddedTextQuality.SUFFICIENT
