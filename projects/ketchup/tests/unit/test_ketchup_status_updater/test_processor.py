"""
Unit tests for AutoStatusProcessor
"""

import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ketchup_status_updater.processor import AutoStatusProcessor


class TestAutoStatusProcessor:
    """Test cases for AutoStatusProcessor"""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for AutoStatusProcessor"""
        return {
            "db_store": MagicMock(),
            "mcp_client": AsyncMock(),
            "secrets_manager": AsyncMock(),
            "slack_config": MagicMock(),
            "openai_handler": AsyncMock(),
            "channel_info_ops": AsyncMock(),
            "channel_msg_ops": AsyncMock(),
            "posting_handler": AsyncMock(),
            "channel_operations": AsyncMock(),
            "channel_membership_ops": AsyncMock(),
            "feature_service": AsyncMock(),
        }

    @pytest.fixture
    def processor(self, mock_dependencies):
        """Create AutoStatusProcessor instance with mocked dependencies"""
        return AutoStatusProcessor(**mock_dependencies)

    @pytest.mark.asyncio
    async def test_should_process_channel_first_run(self, processor):
        """Test channel should be processed on first run"""
        channel = {"channel_id": "C123456", "auto_status_last_run": 0}

        result = await processor._should_process_channel(channel)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_process_channel_due_for_update(self, processor):
        """Test channel should be processed when due for update"""
        # Set last run to 31 minutes ago
        last_run = int((datetime.now() - timedelta(minutes=31)).timestamp())
        channel = {"channel_id": "C123456", "auto_status_last_run": last_run}

        result = await processor._should_process_channel(channel)
        assert result is True

    @pytest.mark.asyncio
    async def test_should_not_process_channel_too_recent(self, processor):
        """Test channel should not be processed when updated recently"""
        # Set last run to 10 minutes ago
        last_run = int((datetime.now() - timedelta(minutes=10)).timestamp())
        channel = {"channel_id": "C123456", "auto_status_last_run": last_run}

        result = await processor._should_process_channel(channel)
        assert result is False

    @patch.dict(os.environ, {"KETCHUP_STATUS_UPDATER_ENABLED": "true"})
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_enabled")
    @pytest.mark.asyncio
    async def test_process_all_channels_when_paused(self, mock_enabled, processor, mock_dependencies):
        """Test process_all_channels returns early when globally paused"""
        mock_enabled.return_value = True

        # Mock pause settings - the processor checks client.get_item first
        mock_dependencies["db_store"].client = AsyncMock()
        mock_dependencies["db_store"].client.get_item = AsyncMock(
            return_value={"Item": {"paused": {"BOOL": True}}}
        )
        mock_dependencies["db_store"].table_name = "test_table"

        result = await processor.process_all_channels()

        assert result["processed"] == 0
        assert "Auto-status is paused" in result["errors"]

    @patch.dict(os.environ, {"KETCHUP_STATUS_UPDATER_ENABLED": "true"})
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_enabled")
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_global")
    @pytest.mark.asyncio
    async def test_process_all_channels_success(self, mock_global, mock_enabled, processor, mock_dependencies):
        """Test successful processing of multiple channels"""
        mock_enabled.return_value = True
        mock_global.return_value = True

        # Mock no pause settings - using client.get_item that raises exception
        mock_dependencies["db_store"].client = AsyncMock()
        mock_dependencies["db_store"].client.get_item = AsyncMock(
            side_effect=Exception("No settings")
        )
        mock_dependencies["db_store"].table_name = "test_table"

        # Mock active channels
        mock_channels = [
            {"channel_id": "C1", "channel_name": "test1", "auto_status_last_run": 0},
            {"channel_id": "C2", "channel_name": "test2", "auto_status_last_run": 0},
        ]
        mock_dependencies["channel_operations"].query_ops.get_all_active_channels = AsyncMock(
            return_value=mock_channels
        )

        # Mock successful processing
        with patch.object(processor, "_should_process_channel", new=AsyncMock(return_value=True)):
            with patch.object(processor, "_process_channel", new=AsyncMock(return_value=True)):
                result = await processor.process_all_channels()

        assert result["processed"] == 2
        assert result["failed"] == 0
        assert result["skipped"] == 0

    @pytest.mark.asyncio
    async def test_process_channel_not_member(self, processor, mock_dependencies):
        """Test skipping channel when bot is not a member"""
        channel = {
            "channel_id": "C123456",
            "channel_name": "test-channel",
            "auto_status_attempt_count": 0,
        }

        # Mock bot not being member of channel
        mock_dependencies["channel_membership_ops"].lookup_membership_of_channels = AsyncMock(
            return_value=[]
        )

        result = await processor._process_channel(channel)
        assert result is False

    @pytest.mark.asyncio
    async def test_process_channel_skip_after_failures(
        self, processor, mock_dependencies
    ):
        """Test that processing is skipped after 5 failures"""
        channel = {
            "channel_id": "C123456",
            "channel_name": "test-channel",
            "auto_status_attempt_count": 5,
            "auto_status_last_content": "Previous status content",
        }

        # Mock bot being member
        mock_dependencies["channel_membership_ops"].lookup_membership_of_channels = AsyncMock(
            return_value=[{"id": "C123456"}]
        )

        # Mock generator
        with patch(
            "ketchup_status_updater.processor.AutoStatusGenerator"
        ) as mock_generator_class:
            mock_generator = mock_generator_class.return_value
            mock_generator.check_for_activity = AsyncMock(return_value={
                "has_activity": True,
                "has_new_messages": True,
                "has_jira_updates": False,
                "latest_message_ts": "1234567890",
                "latest_thread_ts": "1234567890"
            })

            # Mock field update
            mock_dependencies["channel_operations"].update_channel_fields = (
                AsyncMock(return_value=True)
            )

            result = await processor._process_channel(channel)

            # Verify channel is skipped after 5 failures but returns success
            assert result is True
            # Verify generator.generate_and_post_status was NOT called
            mock_generator.generate_and_post_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_channel_increment_attempts_on_failure(
        self, processor, mock_dependencies
    ):
        """Test that attempt count is incremented on failure"""
        channel = {
            "channel_id": "C123456",
            "channel_name": "test-channel",
            "auto_status_attempt_count": 2,
        }

        # Mock bot being member
        mock_dependencies["channel_membership_ops"].lookup_membership_of_channels = AsyncMock(
            return_value=[{"id": "C123456"}]
        )

        # Mock generator to fail
        with patch(
            "ketchup_status_updater.processor.AutoStatusGenerator"
        ) as mock_generator_class:
            mock_generator = mock_generator_class.return_value
            mock_generator.check_for_activity = AsyncMock(return_value={
                "has_activity": True,
                "has_new_messages": True,
                "has_jira_updates": False,
                "latest_message_ts": "1234567890",
                "latest_thread_ts": "1234567890"
            })
            mock_generator.generate_and_post_status = AsyncMock(return_value=False)

            # Mock field update
            mock_dependencies["channel_operations"].update_channel_fields = (
                AsyncMock()
            )

            result = await processor._process_channel(channel)

            # Verify failure and attempt increment
            assert result is False
            update_call = mock_dependencies[
                "channel_operations"
            ].update_channel_fields.call_args
            assert update_call[1]["updates"]["auto_status_attempt_count"] == 3

    @pytest.mark.asyncio
    async def test_process_channel_reset_attempts_on_success(
        self, processor, mock_dependencies
    ):
        """Test that attempt count is reset on success"""
        channel = {
            "channel_id": "C123456",
            "channel_name": "test-channel",
            "auto_status_attempt_count": 3,
        }

        # Mock bot being member
        mock_dependencies["channel_membership_ops"].lookup_membership_of_channels = AsyncMock(
            return_value=[{"id": "C123456"}]
        )

        # Mock generator to succeed
        with patch(
            "ketchup_status_updater.processor.AutoStatusGenerator"
        ) as mock_generator_class:
            mock_generator = mock_generator_class.return_value
            mock_generator.check_for_activity = AsyncMock(return_value={
                "has_activity": True,
                "has_new_messages": True,
                "has_jira_updates": False,
                "latest_message_ts": "1234567890",
                "latest_thread_ts": "1234567890"
            })
            mock_generator.generate_and_post_status = AsyncMock(return_value=True)

            # Mock field update
            mock_dependencies["channel_operations"].update_channel_fields = (
                AsyncMock()
            )

            result = await processor._process_channel(channel)

            # Verify success and fields updated
            assert result is True
            update_call = mock_dependencies[
                "channel_operations"
            ].update_channel_fields.call_args
            assert update_call[1]["updates"]["auto_status_attempt_count"] == 0
            assert "auto_status_last_run" in update_call[1]["updates"]
