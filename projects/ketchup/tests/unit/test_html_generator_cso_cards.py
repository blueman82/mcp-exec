"""Unit tests for HTML generator CSO card rendering."""

from datetime import datetime

import pytest

from packages.core.exports.html_generator import MetricsHTMLGenerator
from packages.slack.models.cso_metrics import CSOChannelCounts, CSOMetrics


class TestCSOCardRendering:
    """Test suite for CSO metric card rendering."""

    @pytest.fixture
    def sample_cso_metrics(self):
        """Create sample CSO metrics."""
        active = CSOChannelCounts(total=4, campaign=4, ajo=0)
        archived = CSOChannelCounts(total=2, campaign=1, ajo=1)
        return CSOMetrics(currently_active=active, archived=archived)

    @pytest.fixture
    def generator(self):
        """Create HTML generator instance."""
        return MetricsHTMLGenerator()

    def test_two_cards_rendered(self, generator, sample_cso_metrics):
        """Test that two separate cards are rendered."""
        # Arrange
        cso = {
            "cso_metrics": sample_cso_metrics,
            "products_using_ketchup": ["campaign", "ajo"],
            "overall_cso_coverage": 100,
            "product_coverage": {
                "campaign": {"channels": 4, "total": 4, "percentage": 100},
                "ajo": {"channels": 1, "total": 1, "percentage": 100},
            },
            "auto_notification_delivery": 95,
        }
        tech = {
            "public_updates": {
                "total_posts": 10,
                "channels_with_updates": 5,
                "success_rate": 90,
            },
            "war_room_messages": {
                "unique_users_per_channel": 20,
                "delivery_rate": 95,
                "total_sent": 100,
            },
            "system_health": {"recently_archived": 2},
        }
        jira = {
            "total_coverage": 80,
            "channels_with_reports": 4,
            "total_channels": 5,
            "posting_details": {
                "primary_only": 2,
                "csopm_only": 1,
                "both_tickets": 1,
                "no_valid_ticket": 1,
                "api_failures": 0,
                "pending": 0,
            },
        }

        # Act
        html = generator.generate(
            cso_metrics=cso,
            technical_metrics=tech,
            jira_metrics=jira,
            period_type="7_days",
            start_date=datetime(2025, 10, 7),
            end_date=datetime(2025, 10, 14),
        )

        # Assert
        assert "Currently Active CSO Channels" in html
        assert "Archived CSO Channels" in html
        # Should have multiple metric cards
        assert html.count("metric-card") >= 2

    def test_currently_active_styling(self, generator, sample_cso_metrics):
        """Test Currently Active card has success (green) styling."""
        # Arrange
        cso = {
            "cso_metrics": sample_cso_metrics,
            "products_using_ketchup": ["campaign"],
            "overall_cso_coverage": 100,
            "product_coverage": {
                "campaign": {"channels": 4, "total": 4, "percentage": 100}
            },
            "auto_notification_delivery": 95,
        }
        tech = {
            "public_updates": {
                "total_posts": 10,
                "channels_with_updates": 5,
                "success_rate": 90,
            },
            "war_room_messages": {
                "unique_users_per_channel": 20,
                "delivery_rate": 95,
                "total_sent": 100,
            },
            "system_health": {"recently_archived": 0},
        }
        jira = {
            "total_coverage": 80,
            "channels_with_reports": 4,
            "total_channels": 5,
            "posting_details": {
                "primary_only": 2,
                "csopm_only": 1,
                "both_tickets": 1,
                "no_valid_ticket": 1,
                "api_failures": 0,
                "pending": 0,
            },
        }

        # Act
        html = generator.generate(
            cso_metrics=cso,
            technical_metrics=tech,
            jira_metrics=jira,
            period_type="7_days",
            start_date=datetime(2025, 10, 7),
            end_date=datetime(2025, 10, 14),
        )

        # Assert - Verify success class appears near Currently Active text
        # Find the index of "Currently Active CSO Channels"
        idx = html.find("Currently Active CSO Channels")
        assert idx > 0
        # Look backwards from that text to find the card definition
        # Success class should be within ~500 chars before the label
        section = html[max(0, idx - 500) : idx + 100]
        assert "metric-card success" in section

    def test_archived_styling(self, generator, sample_cso_metrics):
        """Test Archived card has info (blue) styling."""
        # Arrange
        cso = {
            "cso_metrics": sample_cso_metrics,
            "products_using_ketchup": ["campaign"],
            "overall_cso_coverage": 100,
            "product_coverage": {
                "campaign": {"channels": 4, "total": 4, "percentage": 100}
            },
            "auto_notification_delivery": 95,
        }
        tech = {
            "public_updates": {
                "total_posts": 10,
                "channels_with_updates": 5,
                "success_rate": 90,
            },
            "war_room_messages": {
                "unique_users_per_channel": 20,
                "delivery_rate": 95,
                "total_sent": 100,
            },
            "system_health": {"recently_archived": 0},
        }
        jira = {
            "total_coverage": 80,
            "channels_with_reports": 4,
            "total_channels": 5,
            "posting_details": {
                "primary_only": 2,
                "csopm_only": 1,
                "both_tickets": 1,
                "no_valid_ticket": 1,
                "api_failures": 0,
                "pending": 0,
            },
        }

        # Act
        html = generator.generate(
            cso_metrics=cso,
            technical_metrics=tech,
            jira_metrics=jira,
            period_type="7_days",
            start_date=datetime(2025, 10, 7),
            end_date=datetime(2025, 10, 14),
        )

        # Assert - Verify info class appears near Archived text
        idx = html.find("Archived CSO Channels")
        assert idx > 0
        section = html[max(0, idx - 500) : idx + 100]
        assert "metric-card info" in section

    def test_product_breakdown_displayed(self, generator, sample_cso_metrics):
        """Test product breakdown shows in detail text."""
        # Arrange
        cso = {
            "cso_metrics": sample_cso_metrics,
            "products_using_ketchup": ["campaign", "ajo"],
            "overall_cso_coverage": 100,
            "product_coverage": {
                "campaign": {"channels": 4, "total": 4, "percentage": 100},
                "ajo": {"channels": 1, "total": 1, "percentage": 100},
            },
            "auto_notification_delivery": 95,
        }
        tech = {
            "public_updates": {
                "total_posts": 10,
                "channels_with_updates": 5,
                "success_rate": 90,
            },
            "war_room_messages": {
                "unique_users_per_channel": 20,
                "delivery_rate": 95,
                "total_sent": 100,
            },
            "system_health": {"recently_archived": 0},
        }
        jira = {
            "total_coverage": 80,
            "channels_with_reports": 4,
            "total_channels": 5,
            "posting_details": {
                "primary_only": 2,
                "csopm_only": 1,
                "both_tickets": 1,
                "no_valid_ticket": 1,
                "api_failures": 0,
                "pending": 0,
            },
        }

        # Act
        html = generator.generate(
            cso_metrics=cso,
            technical_metrics=tech,
            jira_metrics=jira,
            period_type="7_days",
            start_date=datetime(2025, 10, 7),
            end_date=datetime(2025, 10, 14),
        )

        # Assert - Product breakdown for Currently Active
        assert "4 Campaign, 0 AJO" in html
        # Product breakdown for Archived
        assert "1 Campaign, 1 AJO" in html

    def test_zero_active_channels(self, generator):
        """Test rendering when no currently active channels."""
        # Arrange
        active = CSOChannelCounts(total=0, campaign=0, ajo=0)
        archived = CSOChannelCounts(total=2, campaign=1, ajo=1)
        cso_metrics = CSOMetrics(currently_active=active, archived=archived)

        cso = {
            "cso_metrics": cso_metrics,
            "products_using_ketchup": ["campaign"],
            "overall_cso_coverage": 0,
            "product_coverage": {
                "campaign": {"channels": 0, "total": 1, "percentage": 0}
            },
            "auto_notification_delivery": 0,
        }
        tech = {
            "public_updates": {
                "total_posts": 0,
                "channels_with_updates": 0,
                "success_rate": 0,
            },
            "war_room_messages": {
                "unique_users_per_channel": 0,
                "delivery_rate": 0,
                "total_sent": 0,
            },
            "system_health": {"recently_archived": 0},
        }
        jira = {
            "total_coverage": 0,
            "channels_with_reports": 0,
            "total_channels": 0,
            "posting_details": {
                "primary_only": 0,
                "csopm_only": 0,
                "both_tickets": 0,
                "no_valid_ticket": 0,
                "api_failures": 0,
                "pending": 0,
            },
        }

        # Act
        html = generator.generate(
            cso_metrics=cso,
            technical_metrics=tech,
            jira_metrics=jira,
            period_type="7_days",
            start_date=datetime(2025, 10, 7),
            end_date=datetime(2025, 10, 14),
        )

        # Assert - Currently Active shows 0
        assert "0 Campaign, 0 AJO" in html

    def test_zero_archived_channels(self, generator):
        """Test rendering when no archived channels."""
        # Arrange
        active = CSOChannelCounts(total=4, campaign=4, ajo=0)
        archived = CSOChannelCounts(total=0, campaign=0, ajo=0)
        cso_metrics = CSOMetrics(currently_active=active, archived=archived)

        cso = {
            "cso_metrics": cso_metrics,
            "products_using_ketchup": ["campaign"],
            "overall_cso_coverage": 100,
            "product_coverage": {
                "campaign": {"channels": 4, "total": 4, "percentage": 100}
            },
            "auto_notification_delivery": 95,
        }
        tech = {
            "public_updates": {
                "total_posts": 10,
                "channels_with_updates": 5,
                "success_rate": 90,
            },
            "war_room_messages": {
                "unique_users_per_channel": 20,
                "delivery_rate": 95,
                "total_sent": 100,
            },
            "system_health": {"recently_archived": 0},
        }
        jira = {
            "total_coverage": 80,
            "channels_with_reports": 4,
            "total_channels": 5,
            "posting_details": {
                "primary_only": 2,
                "csopm_only": 1,
                "both_tickets": 1,
                "no_valid_ticket": 1,
                "api_failures": 0,
                "pending": 0,
            },
        }

        # Act
        html = generator.generate(
            cso_metrics=cso,
            technical_metrics=tech,
            jira_metrics=jira,
            period_type="7_days",
            start_date=datetime(2025, 10, 7),
            end_date=datetime(2025, 10, 14),
        )

        # Assert - Archived shows 0
        # Find section with "Archived CSO Channels"
        idx = html.find("Archived CSO Channels")
        assert idx > 0
        # Look for "0 Campaign, 0 AJO" after archived section
        section = html[idx : idx + 500]
        assert "0 Campaign, 0 AJO" in section
