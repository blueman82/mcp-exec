"""Unit tests for time period parser."""

from datetime import datetime, timezone

from packages.slack.command_processing.command_parameters.time_period_parser import (
    get_month_keys_for_range,
    get_month_start_end,
    get_quarter_start_end,
    parse_month_name,
    parse_quarter,
    parse_year,
)


class TestParseMonthName:
    """Test month name parsing."""

    def test_full_month_names(self):
        """Test full month names."""
        assert parse_month_name("september") == 9
        assert parse_month_name("September") == 9
        assert parse_month_name("SEPTEMBER") == 9

    def test_abbreviations(self):
        """Test common abbreviations."""
        assert parse_month_name("sept") == 9
        assert parse_month_name("sep") == 9
        assert parse_month_name("jan") == 1
        assert parse_month_name("feb") == 2

    def test_too_short(self):
        """Test abbreviations too short."""
        assert parse_month_name("se") is None
        assert parse_month_name("s") is None

    def test_invalid(self):
        """Test invalid month names."""
        assert parse_month_name("xyz") is None
        assert parse_month_name("") is None


class TestParseQuarter:
    """Test quarter parsing."""

    def test_valid_quarters(self):
        """Test valid quarter strings."""
        assert parse_quarter("q1") == 1
        assert parse_quarter("Q2") == 2
        assert parse_quarter("q3") == 3
        assert parse_quarter("Q4") == 4

    def test_invalid_quarters(self):
        """Test invalid quarter strings."""
        assert parse_quarter("q5") is None
        assert parse_quarter("q0") is None
        assert parse_quarter("quarter1") is None
        assert parse_quarter("1") is None


class TestParseYear:
    """Test year parsing."""

    def test_two_digit_years(self):
        """Test 2-digit year conversion."""
        assert parse_year("25") == 2025
        assert parse_year("24") == 2024
        assert parse_year("99") == 2099

    def test_four_digit_years(self):
        """Test 4-digit years."""
        assert parse_year("2025") == 2025
        assert parse_year("2024") == 2024

    def test_invalid_years(self):
        """Test invalid year strings."""
        assert parse_year("abc") is None
        assert parse_year("") is None


class TestGetMonthStartEnd:
    """Test month date range calculation."""

    def test_regular_month(self):
        """Test regular month (30 days)."""
        start, end = get_month_start_end(2025, 9)
        assert start == datetime(2025, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert end == datetime(2025, 9, 30, 23, 59, 59, tzinfo=timezone.utc)

    def test_february_non_leap(self):
        """Test February in non-leap year."""
        start, end = get_month_start_end(2025, 2)
        assert end.day == 28

    def test_february_leap(self):
        """Test February in leap year."""
        start, end = get_month_start_end(2024, 2)
        assert end.day == 29


class TestGetQuarterStartEnd:
    """Test quarter date range calculation."""

    def test_q1_spans_years(self):
        """Test Q1 (Dec-Feb) spans calendar years."""
        start, end = get_quarter_start_end(2025, 1)
        assert start == datetime(2024, 12, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert end == datetime(2025, 2, 28, 23, 59, 59, tzinfo=timezone.utc)

    def test_q2(self):
        """Test Q2 (Mar-May)."""
        start, end = get_quarter_start_end(2025, 2)
        assert start.month == 3
        assert end.month == 5

    def test_q3(self):
        """Test Q3 (Jun-Aug)."""
        start, end = get_quarter_start_end(2025, 3)
        assert start.month == 6
        assert end.month == 8

    def test_q4(self):
        """Test Q4 (Sept-Nov)."""
        start, end = get_quarter_start_end(2025, 4)
        assert start.month == 9
        assert end.month == 11


class TestGetMonthKeysForRange:
    """Test month key generation for date ranges."""

    def test_single_month(self):
        """Test single month range."""
        start = datetime(2025, 9, 1, tzinfo=timezone.utc)
        end = datetime(2025, 9, 30, tzinfo=timezone.utc)
        keys = get_month_keys_for_range(start, end)
        assert keys == ["2025_09"]

    def test_quarter_q1(self):
        """Test Q1 spanning two years."""
        start = datetime(2024, 12, 1, tzinfo=timezone.utc)
        end = datetime(2025, 2, 28, tzinfo=timezone.utc)
        keys = get_month_keys_for_range(start, end)
        assert keys == ["2024_12", "2025_01", "2025_02"]
