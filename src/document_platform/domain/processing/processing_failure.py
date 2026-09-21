"""Safe, bounded evidence for a terminal processing failure."""

from dataclasses import dataclass
from enum import StrEnum


class ProcessingStage(StrEnum):
    UNKNOWN_LEGACY = "UNKNOWN_LEGACY"
    START = "START"
    EMBEDDED_TEXT_EXTRACTION = "EMBEDDED_TEXT_EXTRACTION"
    OCR_TEXT_EXTRACTION = "OCR_TEXT_EXTRACTION"
    TEXT_SELECTION = "TEXT_SELECTION"
    CLASSIFICATION = "CLASSIFICATION"
    INVOICE_EXTRACTION = "INVOICE_EXTRACTION"
    INVOICE_VALIDATION = "INVOICE_VALIDATION"
    VALIDATION_APPLICATION = "VALIDATION_APPLICATION"
    COMPLETION = "COMPLETION"


class ProcessingFailureCode(StrEnum):
    LEGACY_UNCLASSIFIED = "LEGACY_UNCLASSIFIED"
    ACTIVITY_RETRY_EXHAUSTED = "ACTIVITY_RETRY_EXHAUSTED"
    NON_RETRYABLE_ACTIVITY_FAILURE = "NON_RETRYABLE_ACTIVITY_FAILURE"
    ACTIVITY_TIMEOUT = "ACTIVITY_TIMEOUT"


class InvalidProcessingFailure(ValueError):
    """Raised when terminal-failure evidence is not bounded domain data."""


@dataclass(frozen=True, slots=True)
class ProcessingFailure:
    stage: ProcessingStage
    code: ProcessingFailureCode

    def __post_init__(self) -> None:
        if type(self.stage) is not ProcessingStage:
            raise InvalidProcessingFailure("stage must be a ProcessingStage")
        if type(self.code) is not ProcessingFailureCode:
            raise InvalidProcessingFailure("code must be a ProcessingFailureCode")
