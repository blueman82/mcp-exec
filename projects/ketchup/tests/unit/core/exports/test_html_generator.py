"""Unit tests for HTML generator."""

from datetime import datetime, timezone

from packages.core.exports.html_generator import MetricsHTMLGenerator


class TestHTMLGenerator:
    """Test HTML generation with time periods."""

    def test_generates_7_day_dashboard(self):
        """Test 7-day dashboard generation."""
        generator = MetricsHTMLGenerator()

        cso_metrics = {"products_using_ketchup": ["campaign"]}
        technical_metrics = {
            "public_updates": {
                "channels_with_updates": 7,
                "total_posts": None,  # Not available in 7-day
                "success_rate": 100.0,
            }
        }
        jira_metrics = {}

        start = datetime(2025, 10, 3, tzinfo=timezone.utc)
        end = datetime(2025, 10, 10, tzinfo=timezone.utc)

        html = generator.generate(
            cso_metrics,
            technical_metrics,
            jira_metrics,
            period_type="7_days",
            start_date=start,
            end_date=end,
        )

        assert "Past 7 days" in html
        assert "Oct 3 - Oct 10, 2025" in html
        assert "N/A" in html  # Total posts not available

    def test_generates_monthly_dashboard(self):
        """Test monthly dashboard generation."""
        generator = MetricsHTMLGenerator()

        cso_metrics = {"products_using_ketchup": ["campaign"]}
        technical_metrics = {
            "public_updates": {
                "channels_with_updates": 7,
                "total_posts": 45,  # Available in monthly
                "success_rate": 100.0,
            }
        }
        jira_metrics = {}

        start = datetime(2025, 9, 1, tzinfo=timezone.utc)
        end = datetime(2025, 9, 30, tzinfo=timezone.utc)

        html = generator.generate(
            cso_metrics,
            technical_metrics,
            jira_metrics,
            period_type="monthly",
            month=9,
            year=2025,
            is_partial=False,
            start_date=start,
            end_date=end,
        )

        assert "September 2025" in html
        assert "Sept 1 - Sept 30, 2025" in html
        assert "45" in html  # Total posts shown
