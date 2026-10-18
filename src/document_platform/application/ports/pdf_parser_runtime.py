"""Failure types for the replaceable PDF parser runtime."""


class ParserRuntimeUnavailable(RuntimeError):
    """Raised when a parser job cannot be started or reached temporarily."""
