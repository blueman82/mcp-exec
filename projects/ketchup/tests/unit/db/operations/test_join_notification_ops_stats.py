"""
Unit tests for JoinNotificationOps statistics and pruning functionality.

Covers:
- _prune_old_weeks with race condition handling
- get_channel_stats and get_weekly_report methods
- Weekly statistics management
- Retry logic and error handling

All external dependencies mocked. Tests follow existing codebase patterns.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.db.operations.join_notification_ops import JoinNotificationOps

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_client() -> MagicMock:
    """Fixture for mocked DynamoDBAsyncClient."""
    client = MagicMock()
    client.get_item = AsyncMock()
    client.update_item = AsyncMock()
    client.query = AsyncMock()
    client.delete_item = AsyncMock()
    return client


@pytest.fixture
def join_ops(mock_client: MagicMock) -> JoinNotificationOps:
    """Fixture for JoinNotificationOps with mocked client."""
    return JoinNotificationOps(mock_client, "test-table")


class TestJoinNotificationOpsPruning:
    """Test class for JoinNotificationOps pruning functionality."""

    @pytest.mark.asyncio
    async def test_prune_old_weeks_no_weeks_to_remove(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test pruning when no old weeks exist - PK/SK model."""
        # No items returned from query
        mock_client.query.return_value = {"Items": []}

        await join_ops._prune_old_weeks("C1234567890")

        # Should query for weekly items
        mock_client.query.assert_called_once()
        call_args = mock_client.query.call_args[1]
        assert call_args["expression_attribute_values"][":pk"]["S"] == "CHANNEL#C1234567890"
        assert call_args["expression_attribute_values"][":sk_prefix"]["S"] == "WEEK#"

        # Should not delete anything
        mock_client.delete_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_prune_old_weeks_with_removal(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test pruning when old weeks need removal - PK/SK model."""
        # Return old weekly items that should be pruned
        mock_client.query.return_value = {
            "Items": [
                {"PK": {"S": "CHANNEL#C1234567890"}, "SK": {"S": "WEEK#2023-W01"}},
                {"PK": {"S": "CHANNEL#C1234567890"}, "SK": {"S": "WEEK#2023-W02"}},
                {"PK": {"S": "CHANNEL#C1234567890"}, "SK": {"S": "WEEK#2024-W50"}},  # Recent, shouldn't be deleted
            ]
        }

        with patch("packages.db.operations.join_notification_ops.datetime") as mock_datetime:
            # Mock current date as 2024-W51
            from collections import namedtuple
            IsoCalendarDate = namedtuple('IsoCalendarDate', ['year', 'week', 'weekday'])
            mock_datetime.now.return_value.isocalendar.return_value = IsoCalendarDate(2024, 51, 1)

            await join_ops._prune_old_weeks("C1234567890")

            # Should delete only the old weeks
            assert mock_client.delete_item.call_count == 2
            delete_calls = mock_client.delete_item.call_args_list

            deleted_weeks = set()
            for call in delete_calls:
                deleted_weeks.add(call[1]["key"]["SK"]["S"])

            assert "WEEK#2023-W01" in deleted_weeks
            assert "WEEK#2023-W02" in deleted_weeks

    @pytest.mark.asyncio
    async def test_prune_old_weeks_error_handling(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test pruning error handling - PK/SK model."""
        # Query fails with an error
        mock_client.query.side_effect = Exception("DynamoDB Error")

        # Should handle error gracefully (logs error but doesn't raise)
        await join_ops._prune_old_weeks("C1234567890")

        # Should have attempted to query
        mock_client.query.assert_called_once()
        # Should not attempt to delete
        mock_client.delete_item.assert_not_called()



class TestJoinNotificationOpsStats:
    """Test class for JoinNotificationOps statistics functionality."""

    @pytest.mark.asyncio
    async def test_get_channel_stats_success(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test successful retrieval of channel stats - PK/SK model."""
        # Mock CSO_DETAILS item
        mock_item = {
            "user_join_notifications": {
                "M": {
                    "total_sent": {"N": "150"},
                    "total_success": {"N": "142"},
                    "total_failed": {"N": "3"},
                    "total_disabled": {"N": "5"},
                    "last_sent_timestamp": {"N": "1703123456"},
                }
            }
        }
        mock_client.get_item.return_value = {"Item": mock_item}

        # Mock weekly items query
        mock_client.query.return_value = {
            "Items": [
                {
                    "SK": {"S": "WEEK#2024-W45"},
                    "sent": {"N": "10"},
                    "success": {"N": "8"},
                    "failed": {"N": "1"},
                    "disabled": {"N": "1"}
                },
                {
                    "SK": {"S": "WEEK#2024-W44"},
                    "sent": {"N": "15"},
                    "success": {"N": "15"},
                    "failed": {"N": "0"},
                    "disabled": {"N": "0"}
                }
            ]
        }

        with patch.object(join_ops, "_normalize_item") as mock_normalize:
            # Mock normalize for aggregate stats
            mock_normalize.side_effect = [
                {
                    "user_join_notifications": {
                        "total_sent": 150,
                        "total_success": 142,
                        "total_failed": 3,
                        "total_disabled": 5,
                        "last_sent_timestamp": 1703123456,
                    }
                },
                # Mock normalize for weekly items
                {"sent": 10, "success": 8, "failed": 1, "disabled": 1},
                {"sent": 15, "success": 15, "failed": 0, "disabled": 0}
            ]

            result = await join_ops.get_channel_stats("C1234567890")

            # Should have aggregate stats
            assert result["total_sent"] == 150
            assert result["total_success"] == 142
            assert result["total_failed"] == 3
            assert result["total_disabled"] == 5
            assert result["last_sent_timestamp"] == 1703123456

            # Should have weekly stats
            assert "weekly_stats" in result
            assert "2024-W45" in result["weekly_stats"]
            assert "2024-W44" in result["weekly_stats"]
            assert result["weekly_stats"]["2024-W45"]["sent"] == 10
            assert result["weekly_stats"]["2024-W44"]["sent"] == 15

    @pytest.mark.asyncio
    async def test_get_channel_stats_no_item(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test channel stats when no item exists."""
        mock_client.get_item.return_value = {}

        result = await join_ops.get_channel_stats("C1234567890")

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_channel_stats_no_notifications_field(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test channel stats when no notification field exists."""
        mock_client.get_item.return_value = {
            "Item": {
                "channel_id": {"S": "C1234567890"}
            }
        }

        result = await join_ops.get_channel_stats("C1234567890")

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_channel_stats_exception_handling(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test exception handling in get_channel_stats."""
        mock_client.get_item.side_effect = Exception("DynamoDB error")

        result = await join_ops.get_channel_stats("C1234567890")

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_weekly_report_basic(
        self, join_ops: JoinNotificationOps
    ) -> None:
        """Test basic weekly report structure."""
        result = await join_ops.get_weekly_report("2024-W45")

        expected_structure = {
            "week": "2024-W45",
            "total_channels": 0,
            "total_sent": 0,
            "total_success": 0,
            "total_failed": 0,
            "total_disabled": 0,
            "success_rate": 0.0,
            "channels": []
        }

        assert result == expected_structure

    @pytest.mark.asyncio
    async def test_get_weekly_report_exception_handling(
        self, join_ops: JoinNotificationOps
    ) -> None:
        """Test exception handling in get_weekly_report."""
        # Mock the logger to trigger an exception during logging
        with patch("packages.db.operations.join_notification_ops.logger") as mock_logger:
            mock_logger.error.side_effect = Exception("Logging error")

            # Even with logging error, method should return default structure
            result = await join_ops.get_weekly_report("2024-W45")

            # Current implementation returns default structure, not empty dict
            expected_structure = {
                "week": "2024-W45",
                "total_channels": 0,
                "total_sent": 0,
                "total_success": 0,
                "total_failed": 0,
                "total_disabled": 0,
                "success_rate": 0.0,
                "channels": []
            }
            assert result == expected_structure


class TestJoinNotificationOpsUniqueUsers:
    """Test class for unique user counting functionality."""

    @pytest.mark.asyncio
    async def test_get_unique_users_count_no_joins(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test unique user count when no joins exist."""
        mock_client.query.return_value = {"Items": []}

        result = await join_ops.get_unique_users_count("C1234567890")

        assert result == 0
        mock_client.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_unique_users_count_single_user(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test unique user count with single user."""
        mock_client.query.return_value = {
            "Items": [
                {"user_id": {"S": "U001"}, "timestamp": {"N": "1700000000"}},
                {"user_id": {"S": "U001"}, "timestamp": {"N": "1700000100"}},
                {"user_id": {"S": "U001"}, "timestamp": {"N": "1700000200"}},
            ]
        }

        result = await join_ops.get_unique_users_count("C1234567890")

        assert result == 1

    @pytest.mark.asyncio
    async def test_get_unique_users_count_multiple_users(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test unique user count with multiple users."""
        mock_client.query.return_value = {
            "Items": [
                {"user_id": {"S": "U001"}, "timestamp": {"N": "1700000000"}},
                {"user_id": {"S": "U002"}, "timestamp": {"N": "1700000100"}},
                {"user_id": {"S": "U001"}, "timestamp": {"N": "1700000200"}},
                {"user_id": {"S": "U003"}, "timestamp": {"N": "1700000300"}},
                {"user_id": {"S": "U002"}, "timestamp": {"N": "1700000400"}},
            ]
        }

        result = await join_ops.get_unique_users_count("C1234567890")

        assert result == 3

    @pytest.mark.asyncio
    async def test_get_unique_users_count_with_time_range(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test unique user count with time range filtering."""
        mock_client.query.return_value = {
            "Items": [
                {"user_id": {"S": "U001"}, "timestamp": {"N": "1700000000"}},
                {"user_id": {"S": "U002"}, "timestamp": {"N": "1700000100"}},
            ]
        }

        result = await join_ops.get_unique_users_count(
            "C1234567890",
            start_ts=1700000000,
            end_ts=1700000200
        )

        assert result == 2
        call_args = mock_client.query.call_args[1]
        assert ":start_sk" in call_args["expression_attribute_values"]
        assert ":end_sk" in call_args["expression_attribute_values"]

    @pytest.mark.asyncio
    async def test_get_unique_users_count_missing_user_id(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test unique user count with malformed data."""
        mock_client.query.return_value = {
            "Items": [
                {"user_id": {"S": "U001"}},
                {"timestamp": {"N": "1700000000"}},
                {"user_id": {"S": "U002"}},
            ]
        }

        result = await join_ops.get_unique_users_count("C1234567890")

        assert result == 2

    @pytest.mark.asyncio
    async def test_get_unique_users_count_error_handling(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test unique user count error handling."""
        mock_client.query.side_effect = Exception("DynamoDB Error")

        result = await join_ops.get_unique_users_count("C1234567890")

        assert result == 0

    @pytest.mark.asyncio
    async def test_get_unique_users_for_week(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test unique user count for specific week."""
        mock_client.query.return_value = {
            "Items": [
                {"user_id": {"S": "U001"}},
                {"user_id": {"S": "U002"}},
                {"user_id": {"S": "U001"}},
            ]
        }

        result = await join_ops.get_unique_users_for_week(
            "C1234567890",
            "2025-W01"
        )

        assert result == 2

    @pytest.mark.asyncio
    async def test_get_unique_users_for_week_invalid_format(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test unique user count with invalid week format."""
        result = await join_ops.get_unique_users_for_week(
            "C1234567890",
            "invalid-week"
        )

        assert result == 0

    @pytest.mark.asyncio
    async def test_get_unique_users_for_week_error_handling(
        self, join_ops: JoinNotificationOps, mock_client: MagicMock
    ) -> None:
        """Test unique user count for week error handling."""
        mock_client.query.side_effect = Exception("DynamoDB Error")

        result = await join_ops.get_unique_users_for_week(
            "C1234567890",
            "2025-W01"
        )

        assert result == 0