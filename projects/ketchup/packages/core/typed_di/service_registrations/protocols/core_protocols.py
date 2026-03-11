"""Core Infrastructure Protocol Definitions.

This module contains protocol definitions for core infrastructure services
including SecretsManager, SlackConfig, DynamoDB services, and SQS.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class SecretsManagerProtocol(Protocol):
    """Protocol for SecretsManager operations."""

    async def get_slack_api_token_async(self) -> Optional[str]: ...
    async def get_slack_webhook_url(self) -> Optional[str]: ...


@runtime_checkable
class SlackConfigProtocol(Protocol):
    """Protocol for SlackConfig operations."""

    def get_headers(self) -> dict: ...
    def get_api_base_url(self) -> str: ...


@runtime_checkable
class SlackPostingHandlerProtocol(Protocol):
    """Protocol for SlackPostingHandler operations."""

    async def setup(self) -> Any: ...
    async def post_message(self, **kwargs) -> Dict[str, Any]: ...
    async def update_message(self, **kwargs) -> Dict[str, Any]: ...
    async def api_get(self, endpoint: str, params: dict) -> dict: ...
    async def cleanup(self) -> None: ...


@runtime_checkable
class SQSClientProtocol(Protocol):
    """Protocol for SQS client operations."""

    async def send_message(self, message_body: Dict[str, Any]) -> bool: ...
    async def receive_messages(self, max_messages: int = 10) -> List[Dict[str, Any]]: ...
    async def delete_message(self, receipt_handle: str) -> bool: ...
    def get_queue_depth(self) -> int: ...


@runtime_checkable
class DynamoDBConfigProtocol(Protocol):
    """Protocol for DynamoDBConfig operations."""

    pass


@runtime_checkable
class DynamoDBAsyncClientProtocol(Protocol):
    """Protocol for DynamoDBAsyncClient operations."""

    pass


@runtime_checkable
class DynamoDBStoreProtocol(Protocol):
    """Protocol for DynamoDBStore operations."""

    pass


@runtime_checkable
class UserStoreProtocol(Protocol):
    """Protocol for UserStore operations."""

    pass


__all__ = [
    "SecretsManagerProtocol",
    "SlackConfigProtocol",
    "SlackPostingHandlerProtocol",
    "SQSClientProtocol",
    "DynamoDBConfigProtocol",
    "DynamoDBAsyncClientProtocol",
    "DynamoDBStoreProtocol",
    "UserStoreProtocol",
]
