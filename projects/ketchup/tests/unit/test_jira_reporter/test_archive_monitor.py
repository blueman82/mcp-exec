"""
Unit tests for the JIRA reporter channel monitor.

Tests the ChannelMonitor class that identifies channels
needing JIRA reports and handles ticket discovery.
"""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from ketchup_unified_scheduler.services.jira_reporter.channel_monitor import ChannelMonitor
from ketchup_unified_scheduler.services.jira_reporter.ticket_discovery import JiraTicketDiscovery


@pytest.mark.asyncio
class TestChannelMonitor:
    """Test the ChannelMonitor functionality."""

    @pytest.fixture
    def mock_dynamodb_store(self):
        """Create a mock DynamoDB store."""
        store = MagicMock()
        store.channel_ops = MagicMock()
        store.channel_ops.update_jira_report_status = AsyncMock()
        store.update_channel_metadata = AsyncMock()
        store.get_all_channel_details = AsyncMock()
        return store

    @pytest.fixture
    def mock_jira_discovery(self):
        """Create a mock JIRA discovery service."""
        discovery = MagicMock(spec=JiraTicketDiscovery)
        discovery.discover_jira_ticket = AsyncMock()
        return discovery

    @pytest.fixture
    def mock_msg_ops(self):
        """Create a mock message operations service."""
        msg_ops = MagicMock()
        msg_ops.fetch_channel_messages = AsyncMock(return_value=[])
        msg_ops.fetch_channel_messages_collected = AsyncMock(return_value=[])
        msg_ops.latest_message_ts = None
        return msg_ops

    @pytest.fixture
    def channel_monitor(self, mock_dynamodb_store, mock_jira_discovery, mock_msg_ops):
        """Create a ChannelMonitor instance with mocked dependencies."""
        return ChannelMonitor(
            dynamodb_store=mock_dynamodb_store,
            jira_discovery=mock_jira_discovery,
            lookback_hours=24,
            msg_ops=mock_msg_ops,
        )

    async def test_get_channels_needing_reports_filters_non_cso(
        self, channel_monitor, mock_dynamodb_store, mock_msg_ops
    ):
        """Test that non-CSO channels are filtered out."""
        # Arrange
        mock_channels = {
            "C123": {
                "channel_name": "general-discussion",
                "jira_ticket": "CPGNREQ-999",
            },
            "C456": {
                "channel_name": "cso_202501010001_customer_12345",
                "jira_ticket": "CPGNREQ-123",
            },
        }
        mock_dynamodb_store.get_all_channel_details.return_value = mock_channels

        # Mock message activity - channel has been quiet for 25 hours
        mock_msg_ops.get_channel_messages.return_value = [
            {"ts": str(time.time() - (25 * 3600))}  # 25 hours ago
        ]

        # Act
        result = await channel_monitor.get_channels_needing_reports()

        # Assert
        assert len(result) == 1
        assert result[0]["channel_id"] == "C456"
        assert "general-discussion" not in [ch.get("channel_name") for ch in result]

    async def test_get_channels_needing_reports_skips_not_yet_available(
        self, channel_monitor, mock_dynamodb_store
    ):
        """Test that channels with 'NOT YET AVAILABLE' are skipped."""
        # Arrange
        mock_channels = {
            "C789": {
                "channel_name": "cso_202501010002_customer_67890",
                "jira_ticket": "NOT YET AVAILABLE",
            },
            "C790": {
                "channel_name": "cso_202501010003_customer_99999",
                "jira_ticket": "CPGNREQ-790",
            },
        }
        mock_dynamodb_store.get_all_channel_details.return_value = mock_channels

        # Act
        result = await channel_monitor.get_channels_needing_reports()

        # Assert
        assert len(result) == 1
        assert result[0]["channel_id"] == "C790"
        assert result[0]["jira_ticket"] == "CPGNREQ-790"

    async def test_get_channels_needing_reports_skips_processed(
        self, channel_monitor, mock_dynamodb_store
    ):
        """Test that channels already processed are skipped permanently."""
        # Arrange
        mock_channels = {
            "C999": {
                "channel_name": "cso_202501010004_customer_99999",
                "jira_ticket": "CPGNREQ-999",
                "jira_report_status": "PROCESSED",
            },
            "C888": {
                "channel_name": "cso_202501010005_customer_88888",
                "jira_ticket": "CPGNREQ-888",
                "jira_report_status": "",
            },
        }
        mock_dynamodb_store.get_all_channel_details.return_value = mock_channels

        # Act
        result = await channel_monitor.get_channels_needing_reports()

        # Assert
        assert len(result) == 1
        assert result[0]["channel_id"] == "C888"

    async def test_get_channels_needing_reports_checks_activity(
        self, channel_monitor, mock_dynamodb_store, mock_msg_ops
    ):
        """Test that channels with recent activity are skipped."""
        # Arrange
        mock_channels = {
            "C111": {
                "channel_name": "cso_active_incident",
                "jira_ticket": "CPGNREQ-111",
            },
            "C222": {
                "channel_name": "cso_quiet_incident",
                "jira_ticket": "CPGNREQ-222",
            },
        }
        mock_dynamodb_store.get_all_channel_details.return_value = mock_channels

        # Mock different activity levels with proper timestamps
        async def mock_messages(channel_id, limit):
            if channel_id == "C111":
                # Active channel - message 2 hours ago
                return [{"ts": str(time.time() - (2 * 3600))}]
            else:
                # Quiet channel - message 30 hours ago
                return [{"ts": str(time.time() - (30 * 3600))}]

        # Set up both fetch methods to return messages and set latest_message_ts
        async def mock_fetch_messages(channel_id, limit):
            messages = await mock_messages(channel_id, limit)
            if messages:
                mock_msg_ops.latest_message_ts = messages[0]["ts"]
            return messages

        mock_msg_ops.fetch_channel_messages.side_effect = mock_fetch_messages
        mock_msg_ops.fetch_channel_messages_collected.side_effect = mock_fetch_messages

        # Act
        result = await channel_monitor.get_channels_needing_reports()

        # Assert
        assert len(result) == 1
        assert result[0]["channel_id"] == "C222"

    async def test_get_channels_needing_reports_handles_empty_channels(
        self, channel_monitor, mock_dynamodb_store, mock_msg_ops
    ):
        """Test handling of channels with no messages."""
        # Arrange
        mock_channels = {
            "C333": {"channel_name": "cso_empty_channel", "jira_ticket": "CPGNREQ-333"}
        }
        mock_dynamodb_store.get_all_channel_details.return_value = mock_channels

        # Mock empty channel
        mock_msg_ops.get_channel_messages.return_value = []

        # Act
        result = await channel_monitor.get_channels_needing_reports()

        # Assert
        assert len(result) == 1  # Empty channels are considered quiet
        assert result[0]["channel_id"] == "C333"

    async def test_get_channels_needing_reports_error_handling(
        self, channel_monitor, mock_dynamodb_store
    ):
        """Test error handling in get_channels_needing_reports."""
        # Arrange
        mock_dynamodb_store.get_all_channel_details.side_effect = Exception("DB Error")

        # Act
        result = await channel_monitor.get_channels_needing_reports()

        # Assert
        assert result == []  # Returns empty list on error
