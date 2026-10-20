"""Failure types for the replaceable PDF parser runtime."""


class ParserRuntimeUnavailable(RuntimeError):
    """Raised when a parser job cannot be started or reached temporarily."""


class ParserRuntimeRejected(RuntimeError):
    """Raised when parser runtime configuration or controller access is refused."""


class ParserExecutionFailed(RuntimeError):
    """Raised when the isolated parser returns a bounded non-zero exit status."""


class ParserMemoryLimitExceeded(ParserExecutionFailed):
    """Raised when the parser Job reports an observed OOM kill."""


class ParserProcessMemoryLimitExceeded(ParserMemoryLimitExceeded):
    """Raised when a parser process is killed while the container stays alive."""


class ParserContainerMemoryLimitExceeded(ParserMemoryLimitExceeded):
    """Raised when Kubernetes reports the parser container as OOMKilled."""


class ParserOutputExceeded(RuntimeError):
    """Raised when the isolated parser exceeds its configured output bound."""
