"""Application write use cases."""

from document_platform.application.commands.register_document import (
    RegisterDocument,
    RegisterDocumentHandler,
    RegisteredDocument,
)

__all__ = ["RegisterDocument", "RegisterDocumentHandler", "RegisteredDocument"]
