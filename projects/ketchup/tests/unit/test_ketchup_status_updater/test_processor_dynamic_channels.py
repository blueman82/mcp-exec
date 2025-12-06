"""Unit tests for AutoStatusProcessor with dynamic channel filtering."""

import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from ketchup_status_updater.processor import AutoStatusProcessor


class TestProcessorDynamicChannels:
    """Test suite for AutoStatusProcessor dynamic channel filtering."""

    @pytest.fixture
    def mock_dependencies(self, mock_processor_deps):
        """Create mock dependencies for AutoStatusProcessor."""
        return mock_processor_deps

    @pytest.fixture
    def processor(self, mock_processor_deps):
        """Create AutoStatusProcessor instance with mocked dependencies."""
        return AutoStatusProcessor(**mock_processor_deps)

    @patch.dict(os.environ, {"KETCHUP_STATUS_UPDATER_ENABLED": "true"})
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_enabled")
    @pytest.mark.asyncio
    async def test_process_all_channels_feature_disabled(self, mock_enabled, processor):
        """Test that processing stops when feature is disabled."""
        mock_enabled.return_value = False

        result = await processor.process_all_channels()

        assert result["processed"] == 0
        assert result["failed"] == 0
        assert result["skipped"] == 0

    @patch.dict(os.environ, {"KETCHUP_STATUS_UPDATER_ENABLED": "true"})
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_enabled")
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_global")
    @pytest.mark.asyncio
    async def test_process_all_channels_global_mode(
        self, mock_global, mock_enabled, processor, mock_dependencies
    ):
        """Test processing all channels in global mode."""
        mock_enabled.return_value = True
        mock_global.return_value = True

        # Set up channel data for this test
        sample_channels = [
            {"channel_id": "C1234567890", "channel_name": "general", "auto_status_last_run": 0},
            {"channel_id": "C0987654321", "channel_name": "random", "auto_status_last_run": 0},
        ]
        mock_dependencies["channel_operations"].query_ops.get_all_active_channels = AsyncMock(
            return_value=sample_channels
        )

        # Mock processor methods
        processor._should_process_channel = AsyncMock(return_value=True)
        processor._process_channel = AsyncMock(return_value=True)

        result = await processor.process_all_channels()

        assert result["processed"] == 2
        assert processor._process_channel.call_count == 2

    @patch.dict(os.environ, {"KETCHUP_STATUS_UPDATER_ENABLED": "true"})
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_enabled")
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_global")
    @pytest.mark.asyncio
    async def test_process_only_enabled_channels(
        self, mock_global, mock_enabled, processor, mock_dependencies
    ):
        """Test processing only channels with feature enabled."""
        mock_enabled.return_value = True
        mock_global.return_value = False

        # Set up channel data for this test
        sample_channels = [
            {"channel_id": "C1234567890", "channel_name": "general", "auto_status_last_run": 0},
            {"channel_id": "C0987654321", "channel_name": "random", "auto_status_last_run": 0},
            {"channel_id": "C1111111111", "channel_name": "testing", "auto_status_last_run": 0},
        ]
        mock_dependencies["channel_operations"].query_ops.get_all_active_channels = AsyncMock(
            return_value=sample_channels
        )

        # Mock feature service - only first two channels enabled
        processor.feature_service.is_status_updater_enabled_for_channel = AsyncMock(
            side_effect=[True, True, False]
        )

        # Mock processing methods
        processor._should_process_channel = AsyncMock(return_value=True)
        processor._process_channel = AsyncMock(return_value=True)

        result = await processor.process_all_channels()

        assert result["processed"] == 2
        assert processor._process_channel.call_count == 2
        assert processor.feature_service.is_status_updater_enabled_for_channel.call_count == 3

    @patch.dict(os.environ, {"KETCHUP_STATUS_UPDATER_ENABLED": "true"})
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_enabled")
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_global")
    @patch("packages.core.constants.TEST_CHANNEL", "C094DQY7HLH")
    @pytest.mark.asyncio
    async def test_fallback_to_test_channel(
        self, mock_global, mock_enabled, processor, mock_dependencies
    ):
        """Test fallback to TEST_CHANNEL when no channels are enabled."""
        mock_enabled.return_value = True
        mock_global.return_value = False

        # Set up channel data including TEST_CHANNEL
        sample_channels = [
            {"channel_id": "C1234567890", "channel_name": "general", "auto_status_last_run": 0},
            {"channel_id": "C0987654321", "channel_name": "random", "auto_status_last_run": 0},
            {
                "channel_id": "C094DQY7HLH",
                "channel_name": "test-channel",
                "auto_status_last_run": 0,
            },
        ]
        mock_dependencies["channel_operations"].query_ops.get_all_active_channels = AsyncMock(
            return_value=sample_channels
        )

        # Mock feature service - no channels enabled
        processor.feature_service.is_status_updater_enabled_for_channel = AsyncMock(
            return_value=False
        )

        # Mock processing methods
        processor._should_process_channel = AsyncMock(return_value=True)
        processor._process_channel = AsyncMock(return_value=True)

        result = await processor.process_all_channels()

        # Should process only TEST_CHANNEL
        assert result["processed"] == 1
        assert processor._process_channel.call_count == 1
        # Check that it was called with the test channel
        process_call_args = processor._process_channel.call_args[0]
        assert process_call_args[0]["channel_id"] == "C094DQY7HLH"

    @pytest.mark.asyncio
    async def test_should_process_channel_never_run(self, processor):
        """Test _should_process_channel when channel never processed."""
        channel = {"channel_id": "C1234567890", "auto_status_last_run": 0}

        result = await processor._should_process_channel(channel)

        assert result is True

    @pytest.mark.asyncio
    async def test_should_process_channel_due_for_update(self, processor):
        """Test _should_process_channel when channel is due for update."""
        # Set last run to 60 minutes ago
        last_run = datetime.now() - timedelta(minutes=60)
        channel = {
            "channel_id": "C1234567890",
            "auto_status_last_run": int(last_run.timestamp()),
        }

        result = await processor._should_process_channel(channel)

        assert result is True

    @pytest.mark.asyncio
    async def test_should_process_channel_not_due(self, processor):
        """Test _should_process_channel when channel is not due for update."""
        # Set last run to 15 minutes ago (less than 30 minute threshold)
        last_run = datetime.now() - timedelta(minutes=15)
        channel = {
            "channel_id": "C1234567890",
            "auto_status_last_run": int(last_run.timestamp()),
        }

        result = await processor._should_process_channel(channel)

        assert result is False

    @patch.dict(os.environ, {"KETCHUP_STATUS_UPDATER_ENABLED": "true"})
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_enabled")
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_global")
    @pytest.mark.asyncio
    async def test_process_dynamic_channels_success(
        self, mock_global, mock_enabled, processor, mock_dependencies
    ):
        """Test successful processing of dynamic channels."""
        mock_enabled.return_value = True
        mock_global.return_value = True

        # Mock channel operations
        channels = [
            {"channel_id": "C1234567890", "channel_name": "general", "auto_status_last_run": 0},
            {"channel_id": "C0987654321", "channel_name": "random", "auto_status_last_run": 0},
        ]
        mock_dependencies["channel_operations"].query_ops.get_all_active_channels = AsyncMock(
            return_value=channels
        )

        # Mock db_store client for pause check
        mock_dependencies["db_store"].client.get_item = AsyncMock(return_value={})

        # Mock processing methods
        processor._should_process_channel = AsyncMock(return_value=True)
        processor._process_channel = AsyncMock(return_value=True)

        result = await processor.process_all_channels()

        assert result["processed"] == 2
        assert result["failed"] == 0
        assert result["skipped"] == 0
        assert processor._process_channel.call_count == 2

    @patch.dict(os.environ, {"KETCHUP_STATUS_UPDATER_ENABLED": "true"})
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_enabled")
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_global")
    @pytest.mark.asyncio
    async def test_process_dynamic_channels_partial_failure(
        self, mock_global, mock_enabled, processor, mock_dependencies
    ):
        """Test partial failure when processing dynamic channels."""
        mock_enabled.return_value = True
        mock_global.return_value = True

        # Mock channel operations
        channels = [
            {"channel_id": "C1234567890", "channel_name": "general", "auto_status_last_run": 0},
            {"channel_id": "C0987654321", "channel_name": "random", "auto_status_last_run": 0},
            {"channel_id": "C1111111111", "channel_name": "testing", "auto_status_last_run": 0},
        ]
        mock_dependencies["channel_operations"].query_ops.get_all_active_channels = AsyncMock(
            return_value=channels
        )

        # Mock db_store client
        mock_dependencies["db_store"].client.get_item = AsyncMock(return_value={})

        # Mock processing methods - first succeeds, second fails, third succeeds
        processor._should_process_channel = AsyncMock(return_value=True)
        processor._process_channel = AsyncMock(side_effect=[True, False, True])

        result = await processor.process_all_channels()

        assert result["processed"] == 2
        assert result["failed"] == 1
        assert result["skipped"] == 0
        assert processor._process_channel.call_count == 3

    @patch.dict(os.environ, {"KETCHUP_STATUS_UPDATER_ENABLED": "true"})
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_enabled")
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_global")
    @pytest.mark.asyncio
    async def test_process_dynamic_channels_all_fail(
        self, mock_global, mock_enabled, processor, mock_dependencies
    ):
        """Test all channels failing during processing."""
        mock_enabled.return_value = True
        mock_global.return_value = True

        # Mock channel operations
        channels = [
            {"channel_id": "C1234567890", "channel_name": "general", "auto_status_last_run": 0},
            {"channel_id": "C0987654321", "channel_name": "random", "auto_status_last_run": 0},
        ]
        mock_dependencies["channel_operations"].query_ops.get_all_active_channels = AsyncMock(
            return_value=channels
        )

        # Mock db_store client
        mock_dependencies["db_store"].client.get_item = AsyncMock(return_value={})

        # Mock processing methods - all fail
        processor._should_process_channel = AsyncMock(return_value=True)
        processor._process_channel = AsyncMock(return_value=False)

        result = await processor.process_all_channels()

        assert result["processed"] == 0
        assert result["failed"] == 2
        assert result["skipped"] == 0
        assert processor._process_channel.call_count == 2

    @pytest.mark.asyncio
    async def test_should_process_dynamic_channel_first_run(self, processor):
        """Test _should_process_channel for channel that has never been run."""
        channel = {"channel_id": "C1234567890", "auto_status_last_run": 0}

        result = await processor._should_process_channel(channel)

        assert result is True

    @pytest.mark.asyncio
    async def test_should_process_dynamic_channel_recent_update(self, processor):
        """Test _should_process_channel for channel with recent update."""
        # Set last run to 15 minutes ago (less than 30 minute threshold)
        last_run = datetime.now() - timedelta(minutes=15)
        channel = {
            "channel_id": "C1234567890",
            "auto_status_last_run": int(last_run.timestamp()),
        }

        result = await processor._should_process_channel(channel)

        assert result is False

    @patch.dict(os.environ, {"KETCHUP_STATUS_UPDATER_ENABLED": "true"})
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_enabled")
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_global")
    @pytest.mark.asyncio
    async def test_process_specific_dynamic_channels(
        self, mock_global, mock_enabled, processor, mock_dependencies
    ):
        """Test processing specific subset of dynamic channels."""
        mock_enabled.return_value = True
        mock_global.return_value = False  # Non-global mode

        # Mock all channels
        all_channels = [
            {"channel_id": "C1234567890", "channel_name": "general", "auto_status_last_run": 0},
            {"channel_id": "C0987654321", "channel_name": "random", "auto_status_last_run": 0},
            {"channel_id": "C1111111111", "channel_name": "testing", "auto_status_last_run": 0},
        ]
        mock_dependencies["channel_operations"].query_ops.get_all_active_channels = AsyncMock(
            return_value=all_channels
        )

        # Mock feature service - only first two channels enabled
        mock_dependencies["feature_service"].is_status_updater_enabled_for_channel = AsyncMock(
            side_effect=[True, True, False]
        )

        # Mock db_store client
        mock_dependencies["db_store"].client.get_item = AsyncMock(return_value={})

        # Mock processing methods
        processor._should_process_channel = AsyncMock(return_value=True)
        processor._process_channel = AsyncMock(return_value=True)

        result = await processor.process_all_channels()

        # Only first two channels should be processed
        assert result["processed"] == 2
        assert result["failed"] == 0
        assert result["skipped"] == 0
        assert processor._process_channel.call_count == 2

    @patch.dict(os.environ, {"KETCHUP_STATUS_UPDATER_ENABLED": "true"})
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_enabled")
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_global")
    @pytest.mark.asyncio
    async def test_handle_dynamic_channel_errors(
        self, mock_global, mock_enabled, processor, mock_dependencies
    ):
        """Test error handling during dynamic channel processing."""
        mock_enabled.return_value = True
        mock_global.return_value = True

        # Mock channel operations
        channels = [
            {"channel_id": "C1234567890", "channel_name": "general", "auto_status_last_run": 0},
            {"channel_id": "C0987654321", "channel_name": "random", "auto_status_last_run": 0},
        ]
        mock_dependencies["channel_operations"].query_ops.get_all_active_channels = AsyncMock(
            return_value=channels
        )

        # Mock db_store client
        mock_dependencies["db_store"].client.get_item = AsyncMock(return_value={})

        # Mock processing methods - first succeeds, second raises exception
        processor._should_process_channel = AsyncMock(return_value=True)
        processor._process_channel = AsyncMock(side_effect=[True, Exception("Test error")])

        result = await processor.process_all_channels()

        assert result["processed"] == 1
        assert result["failed"] == 1
        assert result["skipped"] == 0
        assert len(result["errors"]) == 1
        assert "Test error" in result["errors"][0]
        assert processor._process_channel.call_count == 2

    @patch.dict(os.environ, {"KETCHUP_STATUS_UPDATER_ENABLED": "true"})
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_enabled")
    @patch("packages.core.config.feature_flags.FeatureFlags.is_status_updater_global")
    @patch("ketchup_status_updater.processor.asyncio.sleep", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_dynamic_channel_pagination(
        self, mock_sleep, mock_global, mock_enabled, processor, mock_dependencies
    ):
        """Test processing large number of channels (pagination simulation)."""
        mock_enabled.return_value = True
        mock_global.return_value = True

        # Mock many channels to simulate pagination
        channels = [
            {"channel_id": f"C{i:010d}", "channel_name": f"channel-{i}", "auto_status_last_run": 0}
            for i in range(50)  # 50 channels
        ]
        mock_dependencies["channel_operations"].query_ops.get_all_active_channels = AsyncMock(
            return_value=channels
        )

        # Mock db_store client
        mock_dependencies["db_store"].client.get_item = AsyncMock(return_value={})

        # Mock processing methods - all succeed
        processor._should_process_channel = AsyncMock(return_value=True)
        processor._process_channel = AsyncMock(return_value=True)

        result = await processor.process_all_channels()

        assert result["processed"] == 50
        assert result["failed"] == 0
        assert result["skipped"] == 0
        assert processor._process_channel.call_count == 50
