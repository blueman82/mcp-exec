"""Unit tests for CSO metrics dataclass models."""

from packages.slack.models.cso_metrics import CSOChannelCounts, CSOMetrics


class TestCSOChannelCounts:
    """Test suite for CSOChannelCounts dataclass."""

    def test_initialization_with_all_fields(self):
        """Test creating CSOChannelCounts with all fields."""
        counts = CSOChannelCounts(total=6, campaign=5, ajo=1)

        assert counts.total == 6
        assert counts.campaign == 5
        assert counts.ajo == 1

    def test_initialization_with_zero_values(self):
        """Test creating CSOChannelCounts with zero values."""
        counts = CSOChannelCounts(total=0, campaign=0, ajo=0)

        assert counts.total == 0
        assert counts.campaign == 0
        assert counts.ajo == 0

    def test_total_matches_sum_of_products(self):
        """Test that total equals campaign + ajo."""
        counts = CSOChannelCounts(total=4, campaign=4, ajo=0)

        # Verify total equals sum
        assert counts.total == counts.campaign + counts.ajo


class TestCSOMetrics:
    """Test suite for CSOMetrics dataclass."""

    def test_initialization_with_both_counts(self):
        """Test creating CSOMetrics with active and archived counts."""
        active = CSOChannelCounts(total=4, campaign=4, ajo=0)
        archived = CSOChannelCounts(total=2, campaign=1, ajo=1)

        metrics = CSOMetrics(currently_active=active, archived=archived)

        assert metrics.currently_active.total == 4
        assert metrics.archived.total == 2

    def test_total_channels_calculation(self):
        """Test total channels across active and archived."""
        active = CSOChannelCounts(total=4, campaign=4, ajo=0)
        archived = CSOChannelCounts(total=2, campaign=1, ajo=1)

        metrics = CSOMetrics(currently_active=active, archived=archived)
        total = metrics.currently_active.total + metrics.archived.total

        assert total == 6

    def test_currently_active_percentage(self):
        """Test percentage of currently active channels."""
        active = CSOChannelCounts(total=4, campaign=4, ajo=0)
        archived = CSOChannelCounts(total=2, campaign=1, ajo=1)

        metrics = CSOMetrics(currently_active=active, archived=archived)
        total = metrics.currently_active.total + metrics.archived.total
        percentage = round((metrics.currently_active.total / total) * 100, 2)

        assert percentage == 66.67  # 4/6 * 100
