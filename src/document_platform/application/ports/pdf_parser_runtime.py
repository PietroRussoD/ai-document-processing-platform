"""Failure types for the replaceable PDF parser runtime."""


class ParserRuntimeUnavailable(RuntimeError):
    """Raised when a parser job cannot be started or reached temporarily."""


class ParserRuntimeRejected(RuntimeError):
    """Raised when parser runtime configuration or controller access is refused."""
