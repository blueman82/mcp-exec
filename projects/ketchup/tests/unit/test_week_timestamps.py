"""
test_week_timestamps.py

Unit tests for weekly timestamp calculation functions.
"""

from datetime import datetime, timezone
from unittest.mock import patch

from packages.db.operations.command_tracking_operations import (
    get_current_week_timestamps,
    get_previous_week_timestamps,
    get_week_date_range,
)


class TestWeekTimestamps:
    """Test suite for week timestamp functions."""

    def test_get_current_week_timestamps_monday(self):
        """Test that Monday is correctly identified as start of week."""
        # Mock a Monday at 10:30 AM UTC
        mock_monday = datetime(2024, 12, 16, 10, 30, 0, tzinfo=timezone.utc)  # Monday, Dec 16, 2024

        with patch("packages.db.operations.command_tracking_operations.dt") as mock_dt:
            mock_dt.now.return_value = mock_monday

            start_ts, end_ts = get_current_week_timestamps()

            # Convert back to datetime for easier assertions
            start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
            end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc)

            # Start should be Monday at 00:00:00
            assert start_dt.year == 2024
            assert start_dt.month == 12
            assert start_dt.day == 16
            assert start_dt.hour == 0
            assert start_dt.minute == 0
            assert start_dt.second == 0

            # End should be Sunday at 23:59:59
            assert end_dt.year == 2024
            assert end_dt.month == 12
            assert end_dt.day == 22
            assert end_dt.hour == 23
            assert end_dt.minute == 59
            assert end_dt.second == 59

    def test_get_current_week_timestamps_sunday(self):
        """Test that Sunday is correctly included in current week."""
        # Mock a Sunday at 8:00 PM UTC
        mock_sunday = datetime(2024, 12, 22, 20, 0, 0, tzinfo=timezone.utc)  # Sunday, Dec 22, 2024

        with patch("packages.db.operations.command_tracking_operations.dt") as mock_dt:
            mock_dt.now.return_value = mock_sunday

            start_ts, end_ts = get_current_week_timestamps()

            # Convert back to datetime
            start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
            end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc)

            # Start should still be Monday Dec 16
            assert start_dt.day == 16

            # End should be same Sunday
            assert end_dt.day == 22

    def test_get_previous_week_timestamps(self):
        """Test previous week calculation."""
        # Mock current time
        mock_now = datetime(2024, 12, 18, 12, 0, 0, tzinfo=timezone.utc)  # Wednesday

        with patch("packages.db.operations.command_tracking_operations.dt") as mock_dt:
            mock_dt.now.return_value = mock_now

            prev_start, prev_end = get_previous_week_timestamps()

            # Previous week should be Dec 9-15
            prev_start_dt = datetime.fromtimestamp(prev_start, tz=timezone.utc)
            prev_end_dt = datetime.fromtimestamp(prev_end, tz=timezone.utc)

            assert prev_start_dt.day == 9  # Monday
            assert prev_end_dt.day == 15  # Sunday at 23:59:59

    def test_get_week_date_range_same_month(self):
        """Test date range formatting when week is in same month."""
        # Dec 16, 2024 (Monday)
        test_date = datetime(2024, 12, 16, tzinfo=timezone.utc)
        timestamp = int(test_date.timestamp())

        with patch("packages.db.operations.command_tracking_operations.dt") as mock_dt:
            mock_dt.fromtimestamp.return_value = test_date

            date_range = get_week_date_range(timestamp)

            assert date_range == "Dec 16-22, 2024"

    def test_get_week_date_range_cross_month(self):
        """Test date range formatting when week crosses months."""
        # Dec 30, 2024 (Monday) - week goes into January
        test_date = datetime(2024, 12, 30, tzinfo=timezone.utc)
        timestamp = int(test_date.timestamp())

        with patch("packages.db.operations.command_tracking_operations.dt") as mock_dt:
            mock_dt.fromtimestamp.return_value = test_date

            date_range = get_week_date_range(timestamp)

            # Should show both months
            assert date_range == "Dec 30 - Jan 05, 2025"

    def test_get_week_date_range_no_timestamp(self):
        """Test date range uses current time when no timestamp provided."""
        mock_now = datetime(2024, 12, 18, 15, 30, 0, tzinfo=timezone.utc)

        with patch("packages.db.operations.command_tracking_operations.dt") as mock_dt:
            mock_dt.now.return_value = mock_now

            date_range = get_week_date_range()

            # Should use current week
            assert date_range == "Dec 16-22, 2024"

    def test_week_boundaries_year_transition(self):
        """Test week calculation at year boundaries."""
        # Dec 31, 2024 is a Tuesday
        mock_new_years_eve = datetime(2024, 12, 31, 12, 0, 0, tzinfo=timezone.utc)

        with patch("packages.db.operations.command_tracking_operations.dt") as mock_dt:
            mock_dt.now.return_value = mock_new_years_eve

            start_ts, end_ts = get_current_week_timestamps()

            start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
            end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc)

            # Week should be Dec 30, 2024 (Mon) to Jan 5, 2025 (Sun)
            assert start_dt.year == 2024
            assert start_dt.month == 12
            assert start_dt.day == 30

            assert end_dt.year == 2025
            assert end_dt.month == 1
            assert end_dt.day == 5
