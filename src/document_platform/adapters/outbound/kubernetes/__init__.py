"""Kubernetes-backed PDF parser runtime adapters."""

from document_platform.adapters.outbound.kubernetes.parser_runtime_connection import (
    KubernetesParserRuntimeConnection,
    KubernetesParserRuntimeSettings,
)

__all__ = ["KubernetesParserRuntimeConnection", "KubernetesParserRuntimeSettings"]
