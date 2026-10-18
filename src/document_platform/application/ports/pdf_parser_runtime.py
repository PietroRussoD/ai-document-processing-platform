"""Failure types for the replaceable PDF parser runtime."""


class ParserRuntimeUnavailable(RuntimeError):
    """Raised when a parser job cannot be started or reached temporarily."""


class ParserRuntimeRejected(RuntimeError):
    """Raised when parser runtime configuration or controller access is refused."""


class ParserExecutionFailed(RuntimeError):
    """Raised when the isolated parser returns a bounded non-zero exit status."""


class ParserOutputExceeded(RuntimeError):
    """Raised when the isolated parser exceeds its configured output bound."""
