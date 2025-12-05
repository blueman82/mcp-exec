"""
Unit tests for the unarchive functionality fix in archive_operations.py

Tests that verify the fix for the bug where unarchive events (archived=False)
were not properly updating the database.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.db.operations.archive_operations import ArchiveOperations


@pytest.mark.asyncio
class TestArchiveOperationsUnarchiveFix:
    """Test the fix for unarchive functionality in ArchiveOperations."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock DynamoDB client."""
        client = MagicMock()
        client.get_item = AsyncMock()
        client.update_item = AsyncMock()
        return client

    @pytest.fixture
    def archive_ops(self, mock_client):
        """Create an ArchiveOperations instance with mocked client."""
        ops = ArchiveOperations(client=mock_client, table_name="test-table")
        return ops

    async def test_unarchive_updates_database(self, archive_ops, mock_client):
        """Test that unarchiving (archived=False) properly updates the database."""
        # Arrange
        channel_id = "C12345"

        # Act
        await archive_ops.update_channel_archived_status(channel_id=channel_id, archived=False)

        # Assert
        mock_client.update_item.assert_awaited_once()
        call_kwargs = mock_client.update_item.call_args.kwargs

        # Verify the correct parameters
        assert call_kwargs["key"] == {
            "PK": {"S": f"CHANNEL#{channel_id}"},
            "SK": {"S": "CSO_DETAILS"},
        }
        assert call_kwargs["update_expression"] == "SET archived = :archived"
        assert call_kwargs["expression_attribute_values"] == {":archived": {"BOOL": False}}
        assert call_kwargs["table_name"] == "test-table"

    async def test_archive_with_timestamp_still_works(self, archive_ops, mock_client):
        """Test that archiving with timestamp still works correctly."""
        # Arrange
        channel_id = "C23456"
        archived_at = 1234567890
        mock_client.get_item.return_value = {"Item": {}}  # No existing archived_at

        # Act
        await archive_ops.update_channel_archived_status(
            channel_id=channel_id, archived=True, archived_at=archived_at
        )

        # Assert
        mock_client.update_item.assert_awaited_once()
        call_kwargs = mock_client.update_item.call_args.kwargs

        assert (
            call_kwargs["update_expression"]
            == "SET archived = :archived, archived_at = :archived_at"
        )
        assert call_kwargs["expression_attribute_values"] == {
            ":archived": {"BOOL": True},
            ":archived_at": {"N": "1234567890"},
        }

    async def test_archive_without_timestamp(self, archive_ops, mock_client):
        """Test that archiving without timestamp works correctly."""
        # Arrange
        channel_id = "C34567"

        # Act
        await archive_ops.update_channel_archived_status(channel_id=channel_id, archived=True)

        # Assert
        mock_client.update_item.assert_awaited_once()
        call_kwargs = mock_client.update_item.call_args.kwargs

        assert call_kwargs["update_expression"] == "SET archived = :archived"
        assert call_kwargs["expression_attribute_values"] == {":archived": {"BOOL": True}}

    async def test_archive_preserves_existing_timestamp(self, archive_ops, mock_client):
        """Test that archiving preserves existing archived_at timestamp."""
        # Arrange
        channel_id = "C45678"
        new_archived_at = 1234567890
        existing_archived_at = "1111111111"

        mock_client.get_item.return_value = {"Item": {"archived_at": {"N": existing_archived_at}}}

        # Act
        await archive_ops.update_channel_archived_status(
            channel_id=channel_id, archived=True, archived_at=new_archived_at
        )

        # Assert
        mock_client.update_item.assert_awaited_once()
        call_kwargs = mock_client.update_item.call_args.kwargs

        assert (
            call_kwargs["expression_attribute_values"][":archived_at"]["N"] == existing_archived_at
        )

    async def test_unarchive_with_archived_at_ignored(self, archive_ops, mock_client):
        """Test that archived_at parameter is ignored when unarchiving."""
        # Arrange
        channel_id = "C56789"

        # Act - archived_at should be ignored for unarchive
        await archive_ops.update_channel_archived_status(
            channel_id=channel_id,
            archived=False,
            archived_at=1234567890,  # This should be ignored
        )

        # Assert
        mock_client.update_item.assert_awaited_once()
        call_kwargs = mock_client.update_item.call_args.kwargs

        # Should only update archived field, not archived_at
        assert call_kwargs["update_expression"] == "SET archived = :archived"
        assert call_kwargs["expression_attribute_values"] == {":archived": {"BOOL": False}}
        assert ":archived_at" not in call_kwargs["expression_attribute_values"]

    async def test_unarchive_error_handling(self, archive_ops, mock_client):
        """Test that errors during unarchive are properly logged."""
        # Arrange
        channel_id = "C67890"
        mock_client.update_item.side_effect = Exception("DynamoDB error")

        # Act - should not raise exception
        await archive_ops.update_channel_archived_status(channel_id=channel_id, archived=False)

        # Assert
        mock_client.update_item.assert_awaited_once()
