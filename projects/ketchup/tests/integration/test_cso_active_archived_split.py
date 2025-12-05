"""Integration test for CSO active vs archived split."""

import asyncio

try:
    import pytest

    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

    # Create dummy decorator for standalone execution
    class pytest:
        class mark:
            @staticmethod
            def asyncio(func):
                return func


from packages.core.exports.html_generator import MetricsHTMLGenerator
from packages.core.typed_di_integration import get_unified_container
from packages.slack.services.metrics_data_collector import MetricsDataCollector


class TestCSOActiveArchivedIntegration:
    """Integration tests for CSO metrics split."""

    @pytest.mark.asyncio
    async def test_collect_cso_metrics_returns_split(self):
        """Test metrics collector returns CSOMetrics with split."""
        # Arrange
        container = await get_unified_container()
        collector = container.get(MetricsDataCollector)

        # Act
        metrics = await collector.collect_cso_metrics(
            start_ts=0, end_ts=9999999999, period_type="7_days"
        )

        # Assert
        assert "cso_metrics" in metrics
        cso_metrics = metrics["cso_metrics"]

        # Verify structure
        assert hasattr(cso_metrics, "currently_active")
        assert hasattr(cso_metrics, "archived")
        assert hasattr(cso_metrics.currently_active, "total")
        assert hasattr(cso_metrics.currently_active, "campaign")
        assert hasattr(cso_metrics.currently_active, "ajo")

        # Verify counts are reasonable
        assert cso_metrics.currently_active.total >= 0
        assert cso_metrics.archived.total >= 0

        print(
            f"✅ Currently Active: {cso_metrics.currently_active.total} "
            f"({cso_metrics.currently_active.campaign} Campaign, "
            f"{cso_metrics.currently_active.ajo} AJO)"
        )
        print(
            f"✅ Archived: {cso_metrics.archived.total} "
            f"({cso_metrics.archived.campaign} Campaign, "
            f"{cso_metrics.archived.ajo} AJO)"
        )

    @pytest.mark.asyncio
    async def test_dashboard_generation_with_split(self):
        """Test dashboard HTML renders with split metrics."""
        # Arrange
        container = await get_unified_container()
        collector = container.get(MetricsDataCollector)
        generator = container.get(MetricsHTMLGenerator)

        # Collect all metrics
        all_metrics = await collector.collect_all_metrics(
            start_ts=0, end_ts=9999999999, period_type="7_days"
        )

        # Act - Generate HTML with MetricsHTMLGenerator
        from datetime import datetime, timezone

        start_date = datetime.fromtimestamp(0, tz=timezone.utc)
        end_date = datetime.fromtimestamp(9999999999, tz=timezone.utc)

        html = generator.generate(
            all_metrics["cso"],
            all_metrics["technical"],
            all_metrics["cso"].get("jira_posting", {}),
            period_type="7_days",
            start_date=start_date,
            end_date=end_date,
        )

        # Assert - Use case-insensitive check since CSS may transform text
        html_lower = html.lower()
        assert "currently active cso channels" in html_lower
        assert "archived cso channels" in html_lower
        assert "campaign" in html_lower or "Campaign" in html
        assert "ajo" in html_lower or "AJO" in html

        print("✅ Dashboard generated with active vs archived split")

    @pytest.mark.asyncio
    async def test_system_channels_excluded(self):
        """Test that system channels are excluded from counts."""
        # Arrange
        container = await get_unified_container()
        collector = container.get(MetricsDataCollector)

        # Act
        metrics = await collector.collect_cso_metrics(
            start_ts=0, end_ts=9999999999, period_type="7_days"
        )

        # Assert - Verify ketchup_access and ketchup_feedback not counted
        # (We can't directly verify exclusion, but counts should match expected)
        cso_metrics = metrics["cso_metrics"]
        total = cso_metrics.currently_active.total + cso_metrics.archived.total

        # Total should not include C090V88CB1N (ketchup_access) or C08CQN1JCSC (ketchup_feedback)
        # In production, we expect ~4-6 channels, not including system channels
        assert total >= 4  # At least 4 real CSO channels
        assert total <= 10  # Not inflated by system channels

        print(f"✅ System channels excluded, total CSO channels: {total}")

    @pytest.mark.asyncio
    async def test_counts_match_dynamodb_query(self):
        """Test that metrics counts match direct DynamoDB query."""
        # Arrange
        container = await get_unified_container()
        collector = container.get(MetricsDataCollector)

        # Act - Get metrics via collector
        metrics = await collector.collect_cso_metrics(
            start_ts=0, end_ts=9999999999, period_type="7_days"
        )
        cso_metrics = metrics["cso_metrics"]

        # Get raw channel data directly from DynamoDB
        from packages.core.config.system_channels import get_excluded_channels
        from packages.db.operations.channel_operations import ChannelOperations

        channel_ops = container.get(ChannelOperations)
        channels = await channel_ops.get_all_channel_details()

        # Filter to CSO channels (campaign/ajo only), excluding system channels
        excluded_channels = get_excluded_channels()
        cso_channels = [
            ch
            for ch_id, ch in channels.items()
            if ch.get("product") in ["campaign", "ajo"] and ch_id not in excluded_channels
        ]

        # Count active vs archived from raw data
        active_count = len([ch for ch in cso_channels if not ch.get("archived", False)])
        archived_count = len([ch for ch in cso_channels if ch.get("archived", False)])

        # Assert - Metrics match direct query
        assert cso_metrics.currently_active.total == active_count
        assert cso_metrics.archived.total == archived_count

        print(f"✅ Counts match DynamoDB query: {active_count} active, {archived_count} archived")


if __name__ == "__main__":
    # Run tests standalone for manual verification
    async def run_tests():
        """Run all tests manually."""
        test_suite = TestCSOActiveArchivedIntegration()

        print("\n" + "=" * 70)
        print("TEST 1: Collect CSO metrics returns split")
        print("=" * 70)
        await test_suite.test_collect_cso_metrics_returns_split()

        print("\n" + "=" * 70)
        print("TEST 2: Dashboard generation with split")
        print("=" * 70)
        await test_suite.test_dashboard_generation_with_split()

        print("\n" + "=" * 70)
        print("TEST 3: System channels excluded")
        print("=" * 70)
        await test_suite.test_system_channels_excluded()

        print("\n" + "=" * 70)
        print("TEST 4: Counts match DynamoDB query")
        print("=" * 70)
        await test_suite.test_counts_match_dynamodb_query()

        print("\n" + "=" * 70)
        print("✅ All integration tests passed!")
        print("=" * 70)

    asyncio.run(run_tests())
