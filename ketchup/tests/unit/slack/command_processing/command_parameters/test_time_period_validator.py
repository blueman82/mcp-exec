"""Unit tests for time period validator."""

from datetime import datetime, timezone, timedelta

from packages.slack.command_processing.command_parameters.time_period_validator import (
    validate_historical_limit,
    validate_not_future,
    validate_time_period,
)


class TestValidateHistoricalLimit:
    """Test historical limit validation."""
    
    def test_current_year_allowed(self):
        """Test current year is allowed."""
        current_year = datetime.now(timezone.utc).year
        is_valid, _ = validate_historical_limit(current_year)
        assert is_valid is True
    
    def test_previous_year_allowed(self):
        """Test previous year is allowed."""
        previous_year = datetime.now(timezone.utc).year - 1
        is_valid, _ = validate_historical_limit(previous_year)
        assert is_valid is True
    
    def test_two_years_ago_rejected(self):
        """Test 2+ years ago is rejected."""
        old_year = datetime.now(timezone.utc).year - 2
        is_valid, error_msg = validate_historical_limit(old_year)
        assert is_valid is False
        assert "only available for current year" in error_msg


class TestValidateNotFuture:
    """Test future date validation."""
    
    def test_past_date_allowed(self):
        """Test past dates are allowed."""
        past_date = datetime.now(timezone.utc) - timedelta(days=30)
        is_valid, _ = validate_not_future(past_date)
        assert is_valid is True
    
    def test_current_date_allowed(self):
        """Test current date is allowed."""
        now = datetime.now(timezone.utc)
        is_valid, _ = validate_not_future(now)
        assert is_valid is True
    
    def test_future_date_rejected(self):
        """Test future dates are rejected."""
        future_date = datetime.now(timezone.utc) + timedelta(days=30)
        is_valid, error_msg = validate_not_future(future_date)
        assert is_valid is False
        assert "Cannot generate metrics for future" in error_msg


class TestValidateTimePeriod:
    """Test combined validation."""
    
    def test_valid_period(self):
        """Test valid time period passes all checks."""
        current_year = datetime.now(timezone.utc).year
        past_date = datetime.now(timezone.utc) - timedelta(days=30)
        is_valid, _ = validate_time_period(current_year, past_date)
        assert is_valid is True
    
    def test_invalid_year_fails(self):
        """Test old year fails validation."""
        old_year = datetime.now(timezone.utc).year - 2
        past_date = datetime(old_year, 6, 1, tzinfo=timezone.utc)
        is_valid, error_msg = validate_time_period(old_year, past_date)
        assert is_valid is False
        assert "only available for current year" in error_msg
    
    def test_future_date_fails(self):
        """Test future date fails validation."""
        future_year = datetime.now(timezone.utc).year + 1
        future_date = datetime(future_year, 6, 1, tzinfo=timezone.utc)
        is_valid, error_msg = validate_time_period(future_year, future_date)
        assert is_valid is False
        assert "Cannot generate metrics for future" in error_msg
