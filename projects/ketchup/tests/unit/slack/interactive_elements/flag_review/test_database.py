"""
Unit tests for FlagReviewDatabaseOperations.

Tests database operations for flag review functionality.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from packages.slack.interactive_elements.flag_review.database import (
    FlagReviewDatabaseOperations,
)


class TestFlagReviewDatabaseOperations:
    """Test suite for FlagReviewDatabaseOperations."""

    @pytest.fixture
    def mock_db_store(self):
        """Create a mock database store."""
        mock = Mock()
        mock.client = Mock()
        mock.client.put_item = AsyncMock(return_value={"ResponseMetadata": {}})
        mock.client.get_item = AsyncMock(return_value={"Item": {}})
        mock.client.query = AsyncMock(return_value={"Items": []})
        mock.client.scan = AsyncMock(return_value={"Items": []})
        mock.client.update_item = AsyncMock(return_value={"ResponseMetadata": {}})
        mock.table_name = "test_table"
        return mock

    @pytest.fixture
    def database_ops(self, mock_db_store):
        """Create database operations with mocked dependencies."""
        return FlagReviewDatabaseOperations(mock_db_store)

    @pytest.mark.asyncio
    async def test_save_flag_review_to_db_success(self, database_ops):
        """Test successful flag review save to database."""
        result = await database_ops.save_flag_review_to_db(
            channel_id="C123",
            message_ts="1234567890.123456",
            user_id="U123",
            user_name="testuser",
            feedback_text="Test feedback",
            validation_issues=[],
            status_text="Test status",
            original_blocks=[],
        )

        assert result["success"] is True
        # Verify database calls were made
        assert database_ops.db_store.client.put_item.call_count >= 1

    @pytest.mark.asyncio
    async def test_get_flag_review_record_exists(self, database_ops):
        """Test retrieving existing flag review record."""
        # Mock record exists via scan method
        database_ops.db_store.client.scan.return_value = {
            "Items": [
                {
                    "flag_id": {"S": "C123_1234567890.123456"},
                    "is_flagged": {"BOOL": True},
                    "flagged_by": {"S": "U123"},
                    "flagged_at": {"S": "2025-01-01T00:00:00Z"},
                }
            ]
        }

        result = await database_ops.get_flag_review_record("C123_1234567890.123456")

        # The method should call the database client via scan
        database_ops.db_store.client.scan.assert_called()
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_flag_review_record_not_exists(self, database_ops):
        """Test retrieving non-existent flag review record."""
        # Mock record doesn't exist
        database_ops.db_store.client.get_item.return_value = {}

        result = await database_ops.get_flag_review_record("C123_1234567890.123456")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_flag_review_status(self, database_ops):
        """Test updating flag review status."""
        # Mock that record exists via scan method
        database_ops.db_store.client.scan.return_value = {
            "Items": [
                {
                    "PK": {"S": "FLAG_REVIEW#test_key"},
                    "SK": {"S": "TIMESTAMP#test_ts"},
                    "flag_id": {"S": "C123_1234567890.123456"},
                }
            ]
        }

        result = await database_ops.update_flag_review_status(
            flag_id="C123_1234567890.123456", status="acknowledged", admin_id="U_ADMIN"
        )

        # Verify database interactions happened
        database_ops.db_store.client.scan.assert_called()
        database_ops.db_store.client.update_item.assert_called()
        assert result is True

    def test_initialization(self, database_ops):
        """Test that database operations initializes correctly."""
        assert database_ops.db_store is not None
        assert hasattr(database_ops, "save_flag_review_to_db")
        assert hasattr(database_ops, "get_flag_review_record")
        assert hasattr(database_ops, "update_flag_review_status")
