"""Unit tests for CSO metrics active vs archived split."""

from unittest.mock import AsyncMock, patch

import pytest

from packages.slack.services.metrics_data_collector import MetricsDataCollector


class TestCSOMetricsSplit:
    """Test suite for active vs archived CSO channel split."""

    @pytest.fixture
    def mock_channel_ops(self):
        """Create mock ChannelOperations."""
        return AsyncMock()

    @pytest.fixture
    def mock_join_ops(self):
        """Create mock JoinNotificationOps."""
        mock = AsyncMock()
        # Mock get_channel_stats to return None (no stats)
        mock.get_channel_stats.return_value = None
        return mock

    @pytest.fixture
    def mock_membership_ops(self):
        """Create mock ChannelMembershipOps."""
        return AsyncMock()

    @pytest.fixture
    def collector(self, mock_channel_ops, mock_join_ops, mock_membership_ops):
        """Create MetricsDataCollector instance."""
        return MetricsDataCollector(
            mock_channel_ops, mock_join_ops, mock_membership_ops
        )

    @pytest.mark.asyncio
    async def test_filter_excluded_channels(self, collector, mock_channel_ops):
        """Test that system channels are excluded from metrics."""
        # Arrange
        # Configure mock to return different data based on archive_lookup parameter
        async def mock_get_channels(archive_lookup=False, days_threshold=None):
            if archive_lookup:
                return {}  # No archived channels
            return {
                "C123": {"product": "campaign", "archived": False},
                "C090V88CB1N": {"product": "campaign", "archived": False},  # Excluded
                "C456": {"product": "ajo", "archived": False},
                "C08CQN1JCSC": {"product": "campaign", "archived": False},  # Excluded
            }

        mock_channel_ops.get_all_channel_details.side_effect = mock_get_channels

        with patch(
            "packages.slack.services.metrics_data_collector.get_excluded_channels"
        ) as mock_excl:
            mock_excl.return_value = {"C090V88CB1N", "C08CQN1JCSC"}

            # Act
            result = await collector.collect_cso_metrics(0, 999999, "7_days")

        # Assert
        cso_metrics = result["cso_metrics"]
        assert cso_metrics.currently_active.total == 2  # Only C123, C456
        # Verify excluded channels not in counts
        assert cso_metrics.currently_active.campaign == 1  # C123 only
        assert cso_metrics.currently_active.ajo == 1  # C456 only

    @pytest.mark.asyncio
    async def test_split_active_vs_archived(self, collector, mock_channel_ops):
        """Test splitting channels by archived status."""
        # Arrange
        # Configure mock to return different data based on archive_lookup parameter
        async def mock_get_channels(archive_lookup=False, days_threshold=None):
            if archive_lookup:
                # Return archived channels when archive_lookup=True
                return {
                    "C003": {"product": "ajo", "archived": True},
                    "C004": {"product": "campaign", "archived": True},
                }
            # Return active channels by default
            return {
                "C001": {"product": "campaign", "archived": False},
                "C002": {"product": "campaign", "archived": False},
            }

        mock_channel_ops.get_all_channel_details.side_effect = mock_get_channels

        with patch(
            "packages.slack.services.metrics_data_collector.get_excluded_channels"
        ) as mock_excl:
            mock_excl.return_value = set()

            # Act
            result = await collector.collect_cso_metrics(0, 999999, "7_days")

        # Assert
        cso_metrics = result["cso_metrics"]
        assert cso_metrics.currently_active.total == 2  # C001, C002
        assert cso_metrics.archived.total == 2  # C003, C004

    @pytest.mark.asyncio
    async def test_count_campaign_vs_ajo_active(self, collector, mock_channel_ops):
        """Test Campaign vs AJO count for currently active channels."""
        # Arrange
        # Configure mock to return different data based on archive_lookup parameter
        async def mock_get_channels(archive_lookup=False, days_threshold=None):
            if archive_lookup:
                return {}  # No archived channels
            return {
                "C001": {"product": "campaign", "archived": False},
                "C002": {"product": "campaign", "archived": False},
                "C003": {"product": "campaign", "archived": False},
                "C004": {"product": "ajo", "archived": False},
            }

        mock_channel_ops.get_all_channel_details.side_effect = mock_get_channels

        with patch(
            "packages.slack.services.metrics_data_collector.get_excluded_channels"
        ) as mock_excl:
            mock_excl.return_value = set()

            # Act
            result = await collector.collect_cso_metrics(0, 999999, "7_days")

        # Assert
        cso_metrics = result["cso_metrics"]
        assert cso_metrics.currently_active.campaign == 3
        assert cso_metrics.currently_active.ajo == 1
        assert cso_metrics.currently_active.total == 4

    @pytest.mark.asyncio
    async def test_count_campaign_vs_ajo_archived(self, collector, mock_channel_ops):
        """Test Campaign vs AJO count for archived channels."""
        # Arrange
        # Configure mock to return different data based on archive_lookup parameter
        async def mock_get_channels(archive_lookup=False, days_threshold=None):
            if archive_lookup:
                # Return archived channels when archive_lookup=True
                return {
                    "C001": {"product": "campaign", "archived": True},
                    "C002": {"product": "ajo", "archived": True},
                    "C003": {"product": "ajo", "archived": True},
                }
            return {}  # No active channels

        mock_channel_ops.get_all_channel_details.side_effect = mock_get_channels

        with patch(
            "packages.slack.services.metrics_data_collector.get_excluded_channels"
        ) as mock_excl:
            mock_excl.return_value = set()

            # Act
            result = await collector.collect_cso_metrics(0, 999999, "7_days")

        # Assert
        cso_metrics = result["cso_metrics"]
        assert cso_metrics.archived.campaign == 1
        assert cso_metrics.archived.ajo == 2
        assert cso_metrics.archived.total == 3

    @pytest.mark.asyncio
    async def test_all_channels_archived(self, collector, mock_channel_ops):
        """Test edge case: all channels archived."""
        # Arrange
        # Configure mock to return different data based on archive_lookup parameter
        async def mock_get_channels(archive_lookup=False, days_threshold=None):
            if archive_lookup:
                # Return archived channels when archive_lookup=True
                return {
                    "C001": {"product": "campaign", "archived": True},
                    "C002": {"product": "ajo", "archived": True},
                }
            return {}  # No active channels

        mock_channel_ops.get_all_channel_details.side_effect = mock_get_channels

        with patch(
            "packages.slack.services.metrics_data_collector.get_excluded_channels"
        ) as mock_excl:
            mock_excl.return_value = set()

            # Act
            result = await collector.collect_cso_metrics(0, 999999, "7_days")

        # Assert
        cso_metrics = result["cso_metrics"]
        assert cso_metrics.currently_active.total == 0
        assert cso_metrics.archived.total == 2

    @pytest.mark.asyncio
    async def test_no_channels_archived(self, collector, mock_channel_ops):
        """Test edge case: no channels archived."""
        # Arrange
        # Configure mock to return different data based on archive_lookup parameter
        async def mock_get_channels(archive_lookup=False, days_threshold=None):
            if archive_lookup:
                return {}  # No archived channels
            return {
                "C001": {"product": "campaign", "archived": False},
                "C002": {"product": "ajo", "archived": False},
            }

        mock_channel_ops.get_all_channel_details.side_effect = mock_get_channels

        with patch(
            "packages.slack.services.metrics_data_collector.get_excluded_channels"
        ) as mock_excl:
            mock_excl.return_value = set()

            # Act
            result = await collector.collect_cso_metrics(0, 999999, "7_days")

        # Assert
        cso_metrics = result["cso_metrics"]
        assert cso_metrics.currently_active.total == 2
        assert cso_metrics.archived.total == 0
        assert cso_metrics.archived.campaign == 0
        assert cso_metrics.archived.ajo == 0

    @pytest.mark.asyncio
    async def test_mixed_scenario(self, collector, mock_channel_ops):
        """Test realistic mixed scenario from production."""
        # Arrange - Real production data structure
        # Configure mock to return different data based on archive_lookup parameter
        async def mock_get_channels(archive_lookup=False, days_threshold=None):
            if archive_lookup:
                # Return archived channels when archive_lookup=True
                return {
                    "C09KKACD6AF": {"product": "ajo", "archived": True},
                    "C09JXUV52MV": {"product": "campaign", "archived": True},
                }
            # Return active channels by default
            return {
                "C09LSLGCDL1": {"product": "campaign", "archived": False},
                "C09KZ231JM9": {"product": "campaign", "archived": False},
                "C09EMM0JP3J": {"product": "campaign", "archived": False},
                "C09KGGH50K0": {"product": "campaign", "archived": False},
                "C090V88CB1N": {"product": "campaign", "archived": False},  # Excluded
                "C09A38VHQTC": {"product": "ajo", "archived": False},
            }

        mock_channel_ops.get_all_channel_details.side_effect = mock_get_channels

        with patch(
            "packages.slack.services.metrics_data_collector.get_excluded_channels"
        ) as mock_excl:
            mock_excl.return_value = {"C090V88CB1N", "C08CQN1JCSC"}

            # Act
            result = await collector.collect_cso_metrics(0, 999999, "7_days")

        # Assert
        cso_metrics = result["cso_metrics"]
        assert cso_metrics.currently_active.total == 5  # 4 campaign + 1 ajo
        assert cso_metrics.currently_active.campaign == 4
        assert cso_metrics.currently_active.ajo == 1
        assert cso_metrics.archived.total == 2  # 1 campaign + 1 ajo
        assert cso_metrics.archived.campaign == 1
        assert cso_metrics.archived.ajo == 1
