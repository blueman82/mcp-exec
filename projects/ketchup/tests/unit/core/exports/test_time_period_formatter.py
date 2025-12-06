"""Unit tests for time period formatter."""

from datetime import datetime, timezone

from packages.core.exports.time_period_formatter import (
    format_confirmation_message,
    format_date_range,
    format_time_period_full,
    format_time_period_label,
)


class TestFormatTimePeriodLabel:
    """Test period label formatting."""

    def test_7_days(self):
        """Test 7-day label."""
        label = format_time_period_label("7_days")
        assert label == "Past 7 days"

    def test_monthly(self):
        """Test monthly label."""
        label = format_time_period_label("monthly", month=9, year=2025)
        assert label == "September 2025"

    def test_quarterly(self):
        """Test quarterly label."""
        label = format_time_period_label("quarterly", quarter=1, year=2025)
        assert label == "Q1 2025"


class TestFormatTimePeriodFull:
    """Test full period description."""

    def test_complete_period(self):
        """Test complete period has no suffix."""
        full = format_time_period_full("monthly", month=9, year=2025, is_partial=False)
        assert full == "September 2025"
        assert "(partial)" not in full

    def test_partial_period(self):
        """Test partial period has suffix."""
        full = format_time_period_full("monthly", month=10, year=2025, is_partial=True)
        assert full == "October 2025 (partial)"


class TestFormatDateRange:
    """Test date range formatting."""

    def test_same_month(self):
        """Test dates in same month."""
        start = datetime(2025, 9, 1, tzinfo=timezone.utc)
        end = datetime(2025, 9, 30, tzinfo=timezone.utc)
        result = format_date_range(start, end)
        assert result == "Sept 1 - Sept 30, 2025"

    def test_different_months_same_year(self):
        """Test dates in different months, same year."""
        start = datetime(2025, 9, 1, tzinfo=timezone.utc)
        end = datetime(2025, 11, 30, tzinfo=timezone.utc)
        result = format_date_range(start, end)
        assert result == "Sept 1 - Nov 30, 2025"

    def test_different_years(self):
        """Test dates spanning years."""
        start = datetime(2024, 12, 1, tzinfo=timezone.utc)
        end = datetime(2025, 2, 28, tzinfo=timezone.utc)
        result = format_date_range(start, end)
        assert result == "Dec 1, 2024 - Feb 28, 2025"


class TestFormatConfirmationMessage:
    """Test confirmation message generation."""

    def test_7_day_message(self):
        """Test 7-day confirmation message."""
        start = datetime(2025, 10, 3, tzinfo=timezone.utc)
        end = datetime(2025, 10, 10, tzinfo=timezone.utc)

        msg = format_confirmation_message("7_days", start_date=start, end_date=end)

        assert "📊 Generating dashboard for:" in msg
        assert "**Past 7 days**" in msg
        assert "Oct 3 - Oct 10, 2025" in msg

    def test_monthly_message(self):
        """Test monthly confirmation message."""
        start = datetime(2025, 9, 1, tzinfo=timezone.utc)
        end = datetime(2025, 9, 30, tzinfo=timezone.utc)

        msg = format_confirmation_message(
            "monthly", month=9, year=2025, is_partial=False, start_date=start, end_date=end
        )

        assert "**September 2025**" in msg
        assert "Sept 1 - Sept 30, 2025" in msg

    def test_quarterly_partial_message(self):
        """Test quarterly partial confirmation message."""
        start = datetime(2025, 9, 1, tzinfo=timezone.utc)
        end = datetime(2025, 10, 10, tzinfo=timezone.utc)

        msg = format_confirmation_message(
            "quarterly", quarter=4, year=2025, is_partial=True, start_date=start, end_date=end
        )

        assert "**Q4 2025 (partial)**" in msg
        assert "Sept 1 - Oct 10, 2025" in msg
