"""
AI Service Protocols

Protocol definitions for AI-related services including Azure OpenAI integration,
prompt management, token counting, cost calculation, embeddings, and analytics.
"""

from typing import Protocol, runtime_checkable

__all__ = [
    "ApiExecutorProtocol",
    "MessagePreparerProtocol",
    "AzureConfigProtocol",
]


@runtime_checkable
class ApiExecutorProtocol(Protocol):
    """Protocol for AI API execution operations."""

    pass


@runtime_checkable
class MessagePreparerProtocol(Protocol):
    """Protocol for message preparation operations."""

    pass


@runtime_checkable
class AzureConfigProtocol(Protocol):
    """Protocol for Azure configuration."""

    pass
