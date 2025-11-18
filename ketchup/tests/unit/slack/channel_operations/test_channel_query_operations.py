"""
Unit tests for channel_query_operations.py in packages.db.operations.

Covers:
- ChannelQueryOperations: _get_targeted_channel, get_channel_details, _get_channels_from_list, _handle_dynamo_error, cleanup
- All logic branches: found, not found, error, batching, unprocessed keys
- All dependencies are mocked
- All tests pass mypy --strict and ruff
- Expected: correct client calls, error handling, logging, batching
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from botocore.exceptions import ClientError

from packages.db.operations.channel_query_operations import ChannelQueryOperations

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_get_targeted_channel_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _get_targeted_channel returns normalized details if found."""
    mock_client = AsyncMock()
    ops = ChannelQueryOperations(client=mock_client, table_name="tbl")
    item = {
        "PK": {"S": "CHANNEL#C1"},
        "SK": {"S": "CSO_DETAILS"},
        "customer_name": {"S": "Acme"},
        "jira_ticket": {"S": "JIRA-1"},
        "channel_name": {"S": "chan"},
    }
    mock_client.get_item = AsyncMock(return_value={"Item": item})
    monkeypatch.setattr(
        ops, "_normalize_item", lambda i: {k: v["S"] for k, v in i.items() if "S" in v}
    )
    with patch("packages.db.operations.channel_query_operations.logger") as mock_logger:
        result = await ops._get_targeted_channel("C1")
        assert result["C1"]["customer_name"] == "Acme"
        assert mock_logger.info.called


@pytest.mark.asyncio
async def test_get_targeted_channel_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _get_targeted_channel returns empty dict if not found."""
    mock_client = AsyncMock()
    ops = ChannelQueryOperations(client=mock_client, table_name="tbl")
    mock_client.get_item = AsyncMock(return_value={})
    with patch("packages.db.operations.channel_query_operations.logger") as mock_logger:
        result = await ops._get_targeted_channel("C2")
        assert result == {}
        assert mock_logger.info.called


@pytest.mark.asyncio
async def test_get_channel_details_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_channel_details returns normalized item if found."""
    mock_client = AsyncMock()
    ops = ChannelQueryOperations(client=mock_client, table_name="tbl")
    item = {"foo": {"S": "bar"}}
    mock_client.get_item = AsyncMock(return_value={"Item": item})
    monkeypatch.setattr(ops, "_normalize_item", lambda i: {"foo": "bar"})
    with patch("packages.db.operations.channel_query_operations.logger") as mock_logger:
        result = await ops.get_channel_details("C3")
        assert result == {"foo": "bar"}
        assert mock_logger.info.called


@pytest.mark.asyncio
async def test_get_channel_details_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_channel_details returns None if not found."""
    mock_client = AsyncMock()
    ops = ChannelQueryOperations(client=mock_client, table_name="tbl")
    mock_client.get_item = AsyncMock(return_value={})
    with patch("packages.db.operations.channel_query_operations.logger") as mock_logger:
        result = await ops.get_channel_details("C4")
        assert result is None
        assert mock_logger.info.called


@pytest.mark.asyncio
async def test_get_channel_details_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test get_channel_details returns None on error."""
    mock_client = AsyncMock()
    ops = ChannelQueryOperations(client=mock_client, table_name="tbl")
    mock_client.get_item = AsyncMock(side_effect=Exception("fail"))
    with patch("packages.db.operations.channel_query_operations.logger") as mock_logger:
        result = await ops.get_channel_details("C5")
        assert result is None
        assert mock_logger.error.called


@pytest.mark.asyncio
async def test_get_channels_from_list_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _get_channels_from_list returns empty dict for empty input."""
    mock_client = AsyncMock()
    ops = ChannelQueryOperations(client=mock_client, table_name="tbl")
    with patch("packages.db.operations.channel_query_operations.logger") as mock_logger:
        result = await ops._get_channels_from_list([])
        assert result == {}
        assert mock_logger.info.called


@pytest.mark.asyncio
async def test_get_channels_from_list_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _get_channels_from_list returns channels for valid input."""
    mock_client = AsyncMock()
    ops = ChannelQueryOperations(client=mock_client, table_name="tbl")
    batch_client = AsyncMock()
    batch_client.batch_get_item = AsyncMock(
        return_value={
            "Responses": {
                "tbl": [{"PK": {"S": "CHANNEL#C6"}, "SK": {"S": "CSO_DETAILS"}}]
            },
            "UnprocessedKeys": {},
        }
    )
    mock_client._get_client = AsyncMock(return_value=batch_client)
    with patch(
        "packages.db.operations.channel_query_operations.logger"
    ) as mock_logger, patch(
        "packages.db.operations.channel_query_operations.MAX_BATCH_SIZE", 25
    ):
        result = await ops._get_channels_from_list(["C6"])
        assert "C6" in result
        assert mock_logger.info.called


@pytest.mark.asyncio
async def test_get_channels_from_list_unprocessed_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _get_channels_from_list retries unprocessed keys."""
    mock_client = AsyncMock()
    ops = ChannelQueryOperations(client=mock_client, table_name="tbl")
    batch_client = AsyncMock()
    # First call returns unprocessed, second call returns processed
    batch_client.batch_get_item = AsyncMock(
        side_effect=[
            {
                "Responses": {"tbl": []},
                "UnprocessedKeys": {
                    "tbl": {
                        "Keys": [
                            {"PK": {"S": "CHANNEL#C7"}, "SK": {"S": "CSO_DETAILS"}}
                        ]
                    }
                },
            },
            {
                "Responses": {
                    "tbl": [{"PK": {"S": "CHANNEL#C7"}, "SK": {"S": "CSO_DETAILS"}}]
                },
                "UnprocessedKeys": {},
            },
        ]
    )
    mock_client._get_client = AsyncMock(return_value=batch_client)
    with patch(
        "packages.db.operations.channel_query_operations.logger"
    ) as mock_logger, patch(
        "packages.db.operations.channel_query_operations.MAX_BATCH_SIZE", 25
    ):
        result = await ops._get_channels_from_list(["C7"])
        assert "C7" in result
        assert mock_logger.warning.called


@pytest.mark.asyncio
async def test_get_channels_from_list_client_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _get_channels_from_list handles ClientError and continues."""
    mock_client = AsyncMock()
    ops = ChannelQueryOperations(client=mock_client, table_name="tbl")
    batch_client = AsyncMock()
    batch_client.batch_get_item = AsyncMock(
        side_effect=ClientError({"Error": {"Message": "fail"}}, "op")
    )
    mock_client._get_client = AsyncMock(return_value=batch_client)
    monkeypatch.setattr(ops, "_handle_dynamo_error", lambda e, op: None)
    with patch(
        "packages.db.operations.channel_query_operations.logger"
    ) as mock_logger, patch(
        "packages.db.operations.channel_query_operations.MAX_BATCH_SIZE", 25
    ):
        result = await ops._get_channels_from_list(["C8"])
        assert result == {}
        assert mock_logger.error.called


@pytest.mark.asyncio
async def test_get_channels_from_list_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test _get_channels_from_list handles Exception and stops processing."""
    mock_client = AsyncMock()
    ops = ChannelQueryOperations(client=mock_client, table_name="tbl")
    batch_client = AsyncMock()
    batch_client.batch_get_item = AsyncMock(side_effect=Exception("fail"))
    mock_client._get_client = AsyncMock(return_value=batch_client)
    with patch(
        "packages.db.operations.channel_query_operations.logger"
    ) as mock_logger, patch(
        "packages.db.operations.channel_query_operations.MAX_BATCH_SIZE", 25
    ):
        result = await ops._get_channels_from_list(["C9"])
        assert result == {}
        assert mock_logger.error.called


def test_handle_dynamo_error_logs() -> None:
    """Test _handle_dynamo_error logs error."""
    mock_client = AsyncMock()
    ops = ChannelQueryOperations(client=mock_client, table_name="tbl")
    error = ClientError({"Error": {"Code": "fail", "Message": "fail"}}, "op")
    with patch("packages.db.operations.channel_query_operations.logger") as mock_logger:
        ops._handle_dynamo_error(error, "optype")
        assert mock_logger.error.called


def test_cleanup_calls_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test cleanup calls parent cleanup and logs debug."""
    mock_client = AsyncMock()
    ops = ChannelQueryOperations(client=mock_client, table_name="tbl")
    parent_cleanup = AsyncMock()
    monkeypatch.setattr(
        "packages.db.operations.base_operations.BaseOperations.cleanup", parent_cleanup
    )
    with patch("packages.db.operations.channel_query_operations.logger") as mock_logger:
        # Call the real method, which should call the parent and log
        asyncio.run(ops.cleanup())
        assert parent_cleanup.called or parent_cleanup.await_count > 0
        assert mock_logger.info.called
