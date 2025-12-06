"""Unit tests for metrics data collector."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.slack.services.metrics_data_collector import MetricsDataCollector


class TestGetMonthlyAggregates:
    """Test monthly aggregate fetching."""

    @pytest.mark.asyncio
    async def test_aggregates_single_month(self):
        """Test aggregating data for a single month."""
        # Setup mocks
        mock_channel_ops = MagicMock()
        mock_channel_ops.client = MagicMock()
        mock_channel_ops.table_name = "test_table"

        mock_join_ops = MagicMock()
        mock_membership_ops = MagicMock()

        collector = MetricsDataCollector(mock_channel_ops, mock_join_ops, mock_membership_ops)

        # Mock the DynamoDBStore.get_monthly_aggregates
        with patch("packages.db.dynamodb_store.DynamoDBStore") as mock_store_class:
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store

            # Mock data for single month
            mock_store.get_monthly_aggregates.return_value = {
                "2025_09": {
                    "auto_status_posts": 10,
                    "war_room_sent": 100,
                    "war_room_success": 95,
                    "war_room_failed": 5,
                    "war_room_unique_users": 30,
                }
            }

            result = await collector._get_monthly_aggregates(["2025_09"])

            assert result["auto_status_posts"] == 10
            assert result["war_room_sent"] == 100
            assert result["war_room_success"] == 95
            assert result["war_room_failed"] == 5
            assert result["war_room_unique_users"] == 30

    @pytest.mark.asyncio
    async def test_aggregates_multiple_months(self):
        """Test aggregating data across multiple months."""
        # Setup mocks
        mock_channel_ops = MagicMock()
        mock_channel_ops.client = MagicMock()
        mock_channel_ops.table_name = "test_table"

        mock_join_ops = MagicMock()
        mock_membership_ops = MagicMock()

        collector = MetricsDataCollector(mock_channel_ops, mock_join_ops, mock_membership_ops)

        # Mock the DynamoDBStore.get_monthly_aggregates
        with patch("packages.db.dynamodb_store.DynamoDBStore") as mock_store_class:
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store

            # Mock data for 2 months
            mock_store.get_monthly_aggregates.return_value = {
                "2025_09": {
                    "auto_status_posts": 10,
                    "war_room_sent": 100,
                    "war_room_success": 95,
                    "war_room_failed": 5,
                    "war_room_unique_users": 30,
                },
                "2025_10": {
                    "auto_status_posts": 15,
                    "war_room_sent": 150,
                    "war_room_success": 145,
                    "war_room_failed": 5,
                    "war_room_unique_users": 40,
                },
            }

            result = await collector._get_monthly_aggregates(["2025_09", "2025_10"])

            assert result["auto_status_posts"] == 25  # 10 + 15
            assert result["war_room_sent"] == 250  # 100 + 150
            assert result["war_room_success"] == 240  # 95 + 145
            assert result["war_room_failed"] == 10  # 5 + 5
            assert result["war_room_unique_users"] == 70  # 30 + 40

    @pytest.mark.asyncio
    async def test_handles_missing_data(self):
        """Test handling of missing monthly data."""
        # Setup mocks
        mock_channel_ops = MagicMock()
        mock_channel_ops.client = MagicMock()
        mock_channel_ops.table_name = "test_table"

        mock_join_ops = MagicMock()
        mock_membership_ops = MagicMock()

        collector = MetricsDataCollector(mock_channel_ops, mock_join_ops, mock_membership_ops)

        # Mock the DynamoDBStore.get_monthly_aggregates
        with patch("packages.db.dynamodb_store.DynamoDBStore") as mock_store_class:
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store

            # Mock empty data (no records for requested month)
            mock_store.get_monthly_aggregates.return_value = {"2025_09": {}}  # Empty metrics

            result = await collector._get_monthly_aggregates(["2025_09"])

            # Should return zeros for all counters
            assert result["auto_status_posts"] == 0
            assert result["war_room_sent"] == 0
            assert result["war_room_success"] == 0
            assert result["war_room_failed"] == 0
            assert result["war_room_unique_users"] == 0

    @pytest.mark.asyncio
    async def test_quarterly_aggregation(self):
        """Test aggregating data for quarterly period (3 months)."""
        # Setup mocks
        mock_channel_ops = MagicMock()
        mock_channel_ops.client = MagicMock()
        mock_channel_ops.table_name = "test_table"

        mock_join_ops = MagicMock()
        mock_membership_ops = MagicMock()

        collector = MetricsDataCollector(mock_channel_ops, mock_join_ops, mock_membership_ops)

        # Mock the DynamoDBStore.get_monthly_aggregates
        with patch("packages.db.dynamodb_store.DynamoDBStore") as mock_store_class:
            mock_store = AsyncMock()
            mock_store_class.return_value = mock_store

            # Mock data for Q4 (Sept, Oct, Nov)
            mock_store.get_monthly_aggregates.return_value = {
                "2025_09": {
                    "auto_status_posts": 10,
                    "war_room_sent": 100,
                    "war_room_success": 95,
                    "war_room_failed": 5,
                    "war_room_unique_users": 30,
                },
                "2025_10": {
                    "auto_status_posts": 15,
                    "war_room_sent": 150,
                    "war_room_success": 145,
                    "war_room_failed": 5,
                    "war_room_unique_users": 40,
                },
                "2025_11": {
                    "auto_status_posts": 20,
                    "war_room_sent": 200,
                    "war_room_success": 195,
                    "war_room_failed": 5,
                    "war_room_unique_users": 50,
                },
            }

            result = await collector._get_monthly_aggregates(["2025_09", "2025_10", "2025_11"])

            assert result["auto_status_posts"] == 45  # 10 + 15 + 20
            assert result["war_room_sent"] == 450  # 100 + 150 + 200
            assert result["war_room_success"] == 435  # 95 + 145 + 195
            assert result["war_room_failed"] == 15  # 5 + 5 + 5
            assert result["war_room_unique_users"] == 120  # 30 + 40 + 50
