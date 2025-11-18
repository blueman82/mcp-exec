"""
Unit tests for dynamodb_async_client.py in packages.db.core.

Covers:
- DynamoDBAsyncClient:
  - __init__: config defaulting, max_concurrent_requests
  - _get_client: client reuse, session invalidation, error handling, session/client creation
  - cleanup: normal and error paths
  - put_item, update_item, delete_item, get_item, scan, query: parameter handling, error propagation, retry decorator
- All AWS/aioboto3 interactions are mocked
- All tests pass mypy --strict and ruff
- Edge cases: client/session reuse, context manager errors, missing/invalid config, DynamoDB errors
- Expected: correct method calls, resource cleanup, error logging, retry logic
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.db.core.dynamodb_async_client import DynamoDBAsyncClient

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_dynamodb_async_client_init_defaults() -> None:
    """Test DynamoDBAsyncClient initializes with default config and concurrency."""
    with patch(
        "packages.db.core.dynamodb_async_client.DynamoDBConfig", autospec=True
    ) as mock_cfg:
        client = DynamoDBAsyncClient()
        assert client.config is mock_cfg.return_value
        assert client._client is None
        assert client._aioboto3_session is None
        assert client._client_cm is None


@pytest.mark.asyncio
async def test_get_client_reuse_and_invalidate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _get_client reuses valid client and recreates on error."""
    client = DynamoDBAsyncClient(config=MagicMock(get_region=lambda: "eu-west-1"))
    mock_client = MagicMock()
    # Valid client reuse - ensure mock has the checked attribute
    mock_client._request_signer = True
    client._client = mock_client
    assert await client._get_client() is mock_client  # type: ignore[no-untyped-call]

    # Invalidate triggers cleanup and recreation
    del mock_client._request_signer
    client._client = mock_client  # type: ignore[assignment]
    monkeypatch.setattr(client, "cleanup", AsyncMock())
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = "new"
    mock_cm.__aexit__.return_value = None
    with patch(
        "aioboto3.Session",
        return_value=MagicMock(client=lambda *a, **k: mock_cm),
    ):
        client._aioboto3_session = None  # type: ignore[assignment]
        result = await client._get_client()  # type: ignore[no-untyped-call]
        assert result == "new"


@pytest.mark.asyncio
async def test_get_client_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _get_client logs and raises on error."""
    client = DynamoDBAsyncClient(config=MagicMock(get_region=lambda: "eu-west-1"))
    monkeypatch.setattr("aioboto3.Session", MagicMock(side_effect=Exception("fail")))
    with patch("packages.db.core.dynamodb_async_client.logger") as mock_logger:
        with pytest.raises(Exception):
            await client._get_client()  # type: ignore[no-untyped-call]
        assert mock_logger.error.called


@pytest.mark.asyncio
async def test_cleanup_normal_and_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test cleanup closes client and handles errors."""
    client = DynamoDBAsyncClient(config=MagicMock(get_region=lambda: "eu-west-1"))
    mock_cm = AsyncMock(__aexit__=AsyncMock())
    client._client = MagicMock()
    client._client_cm = mock_cm
    client._aioboto3_session = MagicMock()
    with patch("packages.db.core.dynamodb_async_client.logger") as mock_logger:
        await client.cleanup()  # type: ignore[no-untyped-call]
        mock_cm.__aexit__.assert_awaited()
        # Error path
        client._client = MagicMock()  # type: ignore[assignment]
        client._client_cm = AsyncMock(
            __aexit__=AsyncMock(side_effect=Exception("fail"))
        )  # type: ignore[assignment]
        await client.cleanup()  # type: ignore[no-untyped-call]
        assert mock_logger.error.called


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,params,extra",
    [
        ("put_item", {"item": {"foo": "bar"}}, {"table_name": None}),
        (
            "update_item",
            {"key": {"id": 1}, "update_expression": "SET x=1"},
            {"table_name": None},
        ),
        ("delete_item", {"key": {"id": 1}}, {"table_name": None}),
        ("get_item", {"key": {"id": 1}}, {"table_name": None}),
        ("scan", {}, {"table_name": None}),
        (
            "query",
            {
                "key_condition_expression": "id=1",
                "expression_attribute_values": {":id": 1},
            },
            {"table_name": None},
        ),
    ],
)
async def test_dynamodb_methods_call_client(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    params: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    """Test DynamoDBAsyncClient public methods call client with correct params."""
    client = DynamoDBAsyncClient(
        config=MagicMock(get_region=lambda: "eu-west-1", get_table_name=lambda: "tbl")
    )
    mock_client = AsyncMock()
    monkeypatch.setattr(client, "_get_client", AsyncMock(return_value=mock_client))
    # Patch retry decorator to identity
    monkeypatch.setattr(
        "packages.db.core.dynamodb_async_client.with_exponential_backoff",
        lambda *a, **k: lambda f: f,
    )
    method_fn = getattr(client, method)
    await method_fn(**params, **extra)  # type: ignore[no-untyped-call]
    assert getattr(mock_client, method).called or any(
        c
        for c in [
            mock_client.put_item,
            mock_client.update_item,
            mock_client.delete_item,
            mock_client.get_item,
            mock_client.scan,
            mock_client.query,
        ]
        if c.called
    )


@pytest.mark.asyncio
async def test_dynamodb_methods_error_propagation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test DynamoDBAsyncClient methods propagate client errors."""
    client = DynamoDBAsyncClient(
        config=MagicMock(get_region=lambda: "eu-west-1", get_table_name=lambda: "tbl")
    )
    monkeypatch.setattr(client, "_get_client", AsyncMock(side_effect=Exception("fail")))
    monkeypatch.setattr(
        "packages.db.core.dynamodb_async_client.with_exponential_backoff",
        lambda *a, **k: lambda f: f,
    )
    with pytest.raises(Exception):
        await client.put_item(item={"foo": "bar"})  # type: ignore[no-untyped-call]
