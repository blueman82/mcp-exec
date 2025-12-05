"""
Unit tests for counter rebuild functionality in JoinNotificationOps.

Tests the rebuild_channel_counters() method that recalculates aggregate
counters from detail records (source of truth).

Covers:
- Rebuilding counters from empty detail records
- Rebuilding counters from various delivery statuses
- Updating DynamoDB with correct SET expressions
- Pagination handling for large datasets

All external dependencies mocked. Tests follow TDD RED-GREEN-REFACTOR cycle.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.db.operations.join_notification_ops import JoinNotificationOps

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_client() -> MagicMock:
    """Fixture for mocked DynamoDBAsyncClient."""
    client = MagicMock()
    client.query = AsyncMock()
    client.update_item = AsyncMock()
    return client


@pytest.fixture
def join_ops(mock_client: MagicMock) -> JoinNotificationOps:
    """Fixture for JoinNotificationOps with mocked client."""
    return JoinNotificationOps(mock_client, "test-table")


class TestCounterRebuild:
    """Test class for counter rebuild functionality."""

    @pytest.mark.asyncio
    async def test_rebuild_counters_from_empty(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test rebuilding counters when no detail records exist."""
        # Arrange - No detail records
        mock_client.query.return_value = {"Items": []}

        # Act
        result = await join_ops.rebuild_channel_counters("C1234567890")

        # Assert - All counters should be zero
        assert result["total_sent"] == 0
        assert result["total_success"] == 0
        assert result["total_failed"] == 0
        assert result["total_disabled"] == 0

        # Verify query was called with correct parameters
        mock_client.query.assert_called_once()
        call_args = mock_client.query.call_args[1]
        assert call_args["expression_attribute_values"][":pk"]["S"] == "USER_JOIN#C1234567890"
        assert call_args["expression_attribute_values"][":sk_prefix"]["S"] == "TS#"

        # Verify update was called with SET expression (overwrites counters)
        mock_client.update_item.assert_called_once()
        update_call = mock_client.update_item.call_args[1]
        assert "SET" in update_call["update_expression"]
        assert "ADD" not in update_call["update_expression"]
        assert update_call["expression_attribute_values"][":sent"]["N"] == "0"
        assert update_call["expression_attribute_values"][":success"]["N"] == "0"
        assert update_call["expression_attribute_values"][":failed"]["N"] == "0"
        assert update_call["expression_attribute_values"][":disabled"]["N"] == "0"

    @pytest.mark.asyncio
    async def test_rebuild_counters_from_detail_records(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test rebuilding counters from detail records with various statuses."""
        # Arrange - 3 success, 1 failed, 1 disabled
        mock_client.query.return_value = {
            "Items": [
                {
                    "PK": {"S": "USER_JOIN#C1234567890"},
                    "SK": {"S": "TS#1700000000#USER#U001"},
                    "notification_attempted": {"BOOL": True},
                    "delivery_status": {"S": "success"},
                },
                {
                    "PK": {"S": "USER_JOIN#C1234567890"},
                    "SK": {"S": "TS#1700000100#USER#U002"},
                    "notification_attempted": {"BOOL": True},
                    "delivery_status": {"S": "success"},
                },
                {
                    "PK": {"S": "USER_JOIN#C1234567890"},
                    "SK": {"S": "TS#1700000200#USER#U003"},
                    "notification_attempted": {"BOOL": True},
                    "delivery_status": {"S": "success"},
                },
                {
                    "PK": {"S": "USER_JOIN#C1234567890"},
                    "SK": {"S": "TS#1700000300#USER#U004"},
                    "notification_attempted": {"BOOL": True},
                    "delivery_status": {"S": "failed"},
                },
                {
                    "PK": {"S": "USER_JOIN#C1234567890"},
                    "SK": {"S": "TS#1700000400#USER#U005"},
                    "notification_attempted": {"BOOL": True},
                    "delivery_status": {"S": "disabled"},
                },
            ]
        }

        # Act
        result = await join_ops.rebuild_channel_counters("C1234567890")

        # Assert - Counters should match detail records
        assert result["total_sent"] == 5
        assert result["total_success"] == 3
        assert result["total_failed"] == 1
        assert result["total_disabled"] == 1

        # Verify update was called with correct values
        mock_client.update_item.assert_called_once()
        update_call = mock_client.update_item.call_args[1]
        assert update_call["expression_attribute_values"][":sent"]["N"] == "5"
        assert update_call["expression_attribute_values"][":success"]["N"] == "3"
        assert update_call["expression_attribute_values"][":failed"]["N"] == "1"
        assert update_call["expression_attribute_values"][":disabled"]["N"] == "1"

    @pytest.mark.asyncio
    async def test_rebuild_counters_updates_dynamodb(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test that rebuild updates DynamoDB with correct parameters."""
        # Arrange - 1 success record
        mock_client.query.return_value = {
            "Items": [
                {
                    "PK": {"S": "USER_JOIN#C1234567890"},
                    "SK": {"S": "TS#1700000000#USER#U001"},
                    "notification_attempted": {"BOOL": True},
                    "delivery_status": {"S": "success"},
                }
            ]
        }

        # Act
        result = await join_ops.rebuild_channel_counters("C1234567890")

        # Assert
        assert result["total_sent"] == 1
        assert result["total_success"] == 1
        assert result["total_failed"] == 0
        assert result["total_disabled"] == 0

        # Verify update_item was called with correct key
        mock_client.update_item.assert_called_once()
        update_call = mock_client.update_item.call_args[1]
        assert update_call["key"]["PK"]["S"] == "CHANNEL#C1234567890"
        assert update_call["key"]["SK"]["S"] == "CSO_DETAILS"

        # Verify SET expression paths
        assert "#ujn.#ts = :sent" in update_call["update_expression"]
        assert "#ujn.#t_success = :success" in update_call["update_expression"]
        assert "#ujn.#t_failed = :failed" in update_call["update_expression"]
        assert "#ujn.#t_disabled = :disabled" in update_call["update_expression"]

        # Verify expression attribute names
        names = update_call["expression_attribute_names"]
        assert names["#ujn"] == "user_join_notifications"
        assert names["#ts"] == "total_sent"
        assert names["#t_success"] == "total_success"
        assert names["#t_failed"] == "total_failed"
        assert names["#t_disabled"] == "total_disabled"

        # Verify expression attribute values (all should be DynamoDB number format)
        values = update_call["expression_attribute_values"]
        assert values[":sent"]["N"] == "1"
        assert values[":success"]["N"] == "1"
        assert values[":failed"]["N"] == "0"
        assert values[":disabled"]["N"] == "0"

    @pytest.mark.asyncio
    async def test_rebuild_counters_handles_pagination(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test that rebuild handles pagination for large datasets."""
        # Arrange - Mock pagination with 2 pages
        mock_client.query.side_effect = [
            {
                "Items": [
                    {
                        "PK": {"S": "USER_JOIN#C1234567890"},
                        "SK": {"S": "TS#1700000000#USER#U001"},
                        "notification_attempted": {"BOOL": True},
                        "delivery_status": {"S": "success"},
                    },
                    {
                        "PK": {"S": "USER_JOIN#C1234567890"},
                        "SK": {"S": "TS#1700000100#USER#U002"},
                        "notification_attempted": {"BOOL": True},
                        "delivery_status": {"S": "failed"},
                    },
                ],
                "LastEvaluatedKey": {
                    "PK": {"S": "USER_JOIN#C1234567890"},
                    "SK": {"S": "TS#1700000100"},
                },
            },
            {
                "Items": [
                    {
                        "PK": {"S": "USER_JOIN#C1234567890"},
                        "SK": {"S": "TS#1700000200#USER#U003"},
                        "notification_attempted": {"BOOL": True},
                        "delivery_status": {"S": "success"},
                    }
                ]
            },
        ]

        # Act
        result = await join_ops.rebuild_channel_counters("C1234567890")

        # Assert - Should count all records across pages
        assert result["total_sent"] == 3
        assert result["total_success"] == 2
        assert result["total_failed"] == 1
        assert result["total_disabled"] == 0

        # Verify query was called twice (pagination)
        assert mock_client.query.call_count == 2

    @pytest.mark.asyncio
    async def test_rebuild_counters_skips_unattempted_notifications(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test that rebuild only counts records with notification_attempted=True."""
        # Arrange - Mix of attempted and unattempted notifications
        mock_client.query.return_value = {
            "Items": [
                {
                    "PK": {"S": "USER_JOIN#C1234567890"},
                    "SK": {"S": "TS#1700000000#USER#U001"},
                    "notification_attempted": {"BOOL": True},
                    "delivery_status": {"S": "success"},
                },
                {
                    "PK": {"S": "USER_JOIN#C1234567890"},
                    "SK": {"S": "TS#1700000100#USER#U002"},
                    "notification_attempted": {"BOOL": False},
                    "delivery_status": {"S": "success"},
                },
                {
                    "PK": {"S": "USER_JOIN#C1234567890"},
                    "SK": {"S": "TS#1700000200#USER#U003"},
                    # Missing notification_attempted field
                    "delivery_status": {"S": "success"},
                },
            ]
        }

        # Act
        result = await join_ops.rebuild_channel_counters("C1234567890")

        # Assert - Should only count the first record
        assert result["total_sent"] == 1
        assert result["total_success"] == 1
        assert result["total_failed"] == 0
        assert result["total_disabled"] == 0

    @pytest.mark.asyncio
    async def test_rebuild_counters_error_handling(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test error handling when query or update fails."""
        # Arrange - Mock query failure
        mock_client.query.side_effect = Exception("DynamoDB Query Error")

        # Act & Assert - Should raise exception
        with pytest.raises(Exception) as exc_info:
            await join_ops.rebuild_channel_counters("C1234567890")

        assert "DynamoDB Query Error" in str(exc_info.value)

        # Verify update was not called
        mock_client.update_item.assert_not_called()
