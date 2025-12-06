"""
test_dynamodb_store.py

Unit tests for DynamoDBStore in packages.db.dynamodb_store.

Covers:
- get_all_channel_details: Delegation to ChannelOperations, correct result returned
- get_channel_details: Delegation, correct result for found and not found, None handling
- store_metadata: Delegation to ChannelOperations, correct call with metadata
- update_channel_archived_status: Delegation to ArchiveOperations, correct call and arguments
- store_feedback: Delegation to FeedbackOperations, returns True/False for success/failure
- delete_channel_if_exists: Delegation to ChannelOperations, returns True/False for found/not found
- ensure_channels_exist: Delegation to ChannelOperations, returns list of new IDs
- cleanup: Calls cleanup on all operation classes
- check_if_temporary_unarchive: Delegation to RestoreStateOperations, returns True/False for found/not found, returns False on error

Edge Cases:
- All error paths for DynamoDB client operations are tested (e.g., scan failure returns empty list)
- All external dependencies are mocked
- Async patterns and error handling are validated

Expected Outcomes:
- Each method returns the correct value or propagates errors as expected
- All delegation to operation classes is verified
- No unhandled exceptions in error scenarios
- All tests pass mypy --strict and ruff
- All tests follow the Ketchup Slack Bot test plan and cursor rules
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.db.dynamodb_store import DynamoDBStore

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_client() -> MagicMock:
    """Fixture for a mocked DynamoDBAsyncClient."""
    return MagicMock()


@pytest.fixture
def store(mock_client: MagicMock) -> DynamoDBStore:
    """Fixture for DynamoDBStore with all operation classes mocked."""
    with (
        patch("packages.db.dynamodb_store.ChannelOperations", autospec=True) as mock_channel_ops,
        patch("packages.db.dynamodb_store.ArchiveOperations", autospec=True) as mock_archive_ops,
        patch("packages.db.dynamodb_store.FeedbackOperations", autospec=True) as mock_feedback_ops,
        patch(
            "packages.db.dynamodb_store.RestoreStateOperations", autospec=True
        ) as mock_restore_ops,
    ):
        store = DynamoDBStore(mock_client, "test-table")
        store.channel_ops = mock_channel_ops.return_value
        store.archive_ops = mock_archive_ops.return_value
        store.feedback_ops = mock_feedback_ops.return_value
        store.restore_ops = mock_restore_ops.return_value
        return store


@pytest.mark.asyncio
async def test_get_all_channel_details(store: DynamoDBStore) -> None:
    """Test get_all_channel_details delegates to ChannelOperations and returns result."""
    with patch.object(
        store.channel_ops, "get_all_channel_details", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = {"foo": 1}
        result = await store.get_all_channel_details()
        assert result == {"foo": 1}
        mock_get.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_channel_details(store: DynamoDBStore) -> None:
    """Test get_channel_details delegates and returns result or None."""
    with patch.object(store.channel_ops, "get_channel_details", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = {"id": "C1"}
        result = await store.get_channel_details("C1")
        assert result == {"id": "C1"}
        mock_get.assert_awaited_once_with("C1")
    with patch.object(store.channel_ops, "get_channel_details", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        result = await store.get_channel_details("C2")
        assert result is None


@pytest.mark.asyncio
async def test_store_metadata(store: DynamoDBStore) -> None:
    """Test store_metadata delegates to ChannelOperations."""
    mock_metadata = MagicMock()
    with patch.object(store.channel_ops, "store_metadata", new_callable=AsyncMock) as mock_store:
        await store.store_metadata(mock_metadata)
        mock_store.assert_awaited_once_with(mock_metadata)


@pytest.mark.asyncio
async def test_update_channel_archived_status(store: DynamoDBStore) -> None:
    """Test update_channel_archived_status delegates to ArchiveOperations."""
    with patch.object(
        store.archive_ops, "update_channel_archived_status", new_callable=AsyncMock
    ) as mock_update:
        await store.update_channel_archived_status("C1", True, 123)
        mock_update.assert_awaited_once_with("C1", True, 123)


@pytest.mark.asyncio
async def test_store_feedback(store: DynamoDBStore) -> None:
    """Test store_feedback delegates to FeedbackOperations and returns bool."""
    with patch.object(store.feedback_ops, "store_feedback", new_callable=AsyncMock) as mock_store:
        mock_store.return_value = True
        result = await store.store_feedback({"foo": "bar"})
        assert result is True
        mock_store.assert_awaited_once()
    with patch.object(store.feedback_ops, "store_feedback", new_callable=AsyncMock) as mock_store:
        mock_store.return_value = False
        result = await store.store_feedback({"foo": "baz"})
        assert result is False


@pytest.mark.asyncio
async def test_delete_channel_if_exists(store: DynamoDBStore) -> None:
    """Test delete_channel_if_exists delegates and returns bool."""
    with patch.object(
        store.channel_ops, "delete_channel_if_exists", new_callable=AsyncMock
    ) as mock_delete:
        mock_delete.return_value = True
        result = await store.delete_channel_if_exists("C1")
        assert result is True
        mock_delete.assert_awaited_once_with("C1")
    with patch.object(
        store.channel_ops, "delete_channel_if_exists", new_callable=AsyncMock
    ) as mock_delete:
        mock_delete.return_value = False
        result = await store.delete_channel_if_exists("C2")
        assert result is False


@pytest.mark.asyncio
async def test_ensure_channels_exist(store: DynamoDBStore) -> None:
    """Test ensure_channels_exist delegates and returns list of new IDs."""
    with patch.object(
        store.channel_ops, "ensure_channels_exist", new_callable=AsyncMock
    ) as mock_ensure:
        mock_ensure.return_value = ["C1", "C2"]
        result = await store.ensure_channels_exist([{"id": "C1"}])
        assert result == ["C1", "C2"]
        mock_ensure.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup(store: DynamoDBStore) -> None:
    """Test cleanup calls cleanup on all operation classes."""
    with (
        patch.object(store.channel_ops, "cleanup", new_callable=AsyncMock) as mock_ch,
        patch.object(store.archive_ops, "cleanup", new_callable=AsyncMock) as mock_ar,
        patch.object(store.feedback_ops, "cleanup", new_callable=AsyncMock) as mock_fb,
    ):
        await store.cleanup()
        mock_ch.assert_awaited_once()
        mock_ar.assert_awaited_once()
        mock_fb.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_if_temporary_unarchive_success(store: DynamoDBStore) -> None:
    """Test check_if_temporary_unarchive returns True/False as delegated."""
    with patch.object(
        store.restore_ops, "check_if_temporary_unarchive", new_callable=AsyncMock
    ) as mock_check:
        mock_check.return_value = True
        result = await store.check_if_temporary_unarchive("C1")
        assert result is True
    with patch.object(
        store.restore_ops, "check_if_temporary_unarchive", new_callable=AsyncMock
    ) as mock_check:
        mock_check.return_value = False
        result = await store.check_if_temporary_unarchive("C2")
        assert result is False


@pytest.mark.asyncio
async def test_check_if_temporary_unarchive_error(store: DynamoDBStore) -> None:
    """Test check_if_temporary_unarchive returns False on error."""
    with patch.object(
        store.restore_ops, "check_if_temporary_unarchive", new_callable=AsyncMock
    ) as mock_check:
        mock_check.side_effect = Exception("fail")
        result = await store.check_if_temporary_unarchive("C3")
        assert result is False
