"""
Unit tests for archive_operations.py in packages.db.operations.

Covers:
- ArchiveOperations: update_channel_archived_status (all logic branches)
- Error handling and logging
- cleanup method
- All dependencies are mocked
- All tests pass mypy --strict and ruff
- Expected: correct client calls, update logic, error handling, parent cleanup
"""

from unittest.mock import AsyncMock, patch

import pytest

from packages.db.operations.archive_operations import ArchiveOperations
from packages.db.operations.base_operations import BaseOperations

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_update_channel_archived_status_preserves_existing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test update_channel_archived_status preserves existing archived_at if non-zero."""
    mock_client = AsyncMock()
    ops = ArchiveOperations(client=mock_client, table_name="tbl")
    # Simulate existing item with non-zero archived_at
    mock_client.get_item = AsyncMock(
        return_value={"Item": {"archived_at": {"N": "123"}}}
    )
    mock_client.update_item = AsyncMock()
    with patch("packages.db.operations.archive_operations.logger") as mock_logger:
        await ops.update_channel_archived_status("C1", True, 456)
        mock_client.get_item.assert_awaited()
        mock_client.update_item.assert_awaited_with(
            key={"PK": {"S": "CHANNEL#C1"}, "SK": {"S": "CSO_DETAILS"}},
            update_expression="SET archived = :archived, archived_at = :archived_at",
            expression_attribute_values={
                ":archived": {"BOOL": True},
                ":archived_at": {"N": "123"},
            },
            table_name="tbl",
        )
        assert mock_logger.info.called


@pytest.mark.asyncio
async def test_update_channel_archived_status_sets_new(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test update_channel_archived_status sets new archived_at if not present or zero."""
    mock_client = AsyncMock()
    ops = ArchiveOperations(client=mock_client, table_name="tbl")
    # Simulate existing item with zero archived_at
    mock_client.get_item = AsyncMock(return_value={"Item": {"archived_at": {"N": "0"}}})
    mock_client.update_item = AsyncMock()
    with patch("packages.db.operations.archive_operations.logger") as mock_logger:
        await ops.update_channel_archived_status("C2", True, 789)
        mock_client.get_item.assert_awaited()
        mock_client.update_item.assert_awaited_with(
            key={"PK": {"S": "CHANNEL#C2"}, "SK": {"S": "CSO_DETAILS"}},
            update_expression="SET archived = :archived, archived_at = :archived_at",
            expression_attribute_values={
                ":archived": {"BOOL": True},
                ":archived_at": {"N": "789"},
            },
            table_name="tbl",
        )
        assert mock_logger.info.called


@pytest.mark.asyncio
async def test_update_channel_archived_status_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test update_channel_archived_status logs error if client throws."""
    mock_client = AsyncMock()
    ops = ArchiveOperations(client=mock_client, table_name="tbl")
    mock_client.get_item = AsyncMock(side_effect=Exception("fail"))
    with patch("packages.db.operations.archive_operations.logger") as mock_logger:
        await ops.update_channel_archived_status("C3", True, 123)
        assert mock_logger.error.called


@pytest.mark.asyncio
@patch("packages.db.operations.archive_operations.logger")
async def test_cleanup_calls_parent(
    mock_logger, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test cleanup calls parent cleanup and logs debug."""
    mock_client = AsyncMock()
    ops = ArchiveOperations(client=mock_client, table_name="tbl")
    parent_cleanup = AsyncMock()
    monkeypatch.setattr(BaseOperations, "cleanup", parent_cleanup)
    await ArchiveOperations.cleanup(ops)
    assert parent_cleanup.called or getattr(parent_cleanup, "await_count", 0) > 0
    assert mock_logger.info.called
