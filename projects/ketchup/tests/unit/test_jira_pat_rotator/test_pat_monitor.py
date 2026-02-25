#!/usr/bin/env python3
"""
Tests for PAT expiry monitor.

Verifies:
- Correctly calculates days until PAT expiry
- Detects when <= 15 days remaining and rotation is needed
- Handles missing JIRA_PAT_EXPIRY gracefully
- Parses ISO 8601 date strings correctly
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from ketchup_unified_scheduler.services.pat_rotator.monitor import PatMonitor


class TestPatExpiryCalculation:
    """Tests for PAT expiry date calculation."""

    def test_correctly_calculates_days_until_expiry(self):
        """Test that days until expiry is calculated correctly."""
        monitor = PatMonitor()

        # Set expiry date to 90 days in the future
        expiry_date = datetime.now(timezone.utc) + timedelta(days=90)
        expiry_iso = expiry_date.isoformat()

        days_remaining = monitor._calculate_days_remaining(expiry_iso)

        # Should be approximately 90 days (within 1 day tolerance for time drift)
        assert 89 <= days_remaining <= 90

    def test_correctly_calculates_days_when_close_to_expiry(self):
        """Test days calculation when close to expiry date."""
        monitor = PatMonitor()

        # Set expiry date to 5 days in the future
        expiry_date = datetime.now(timezone.utc) + timedelta(days=5)
        expiry_iso = expiry_date.isoformat()

        days_remaining = monitor._calculate_days_remaining(expiry_iso)

        assert 4 <= days_remaining <= 5

    def test_correctly_calculates_days_when_expired(self):
        """Test days calculation when PAT is already expired."""
        monitor = PatMonitor()

        # Set expiry date to 5 days in the past
        expiry_date = datetime.now(timezone.utc) - timedelta(days=5)
        expiry_iso = expiry_date.isoformat()

        days_remaining = monitor._calculate_days_remaining(expiry_iso)

        # Should be negative
        assert days_remaining < 0


class TestRotationNeeded:
    """Tests for detecting when PAT rotation is needed."""

    def test_detects_rotation_needed_when_less_than_15_days_remaining(self):
        """Test that rotation is needed when < 15 days remaining."""
        monitor = PatMonitor()

        # Set expiry date to 10 days in the future (less than 15-day buffer)
        expiry_date = datetime.now(timezone.utc) + timedelta(days=10)
        expiry_iso = expiry_date.isoformat()

        with patch.object(monitor, "_get_pat_expiry_from_secrets", return_value=expiry_iso):
            result = monitor.should_rotate()

            assert result is True

    def test_detects_no_rotation_needed_when_more_than_15_days_remaining(self):
        """Test that rotation is not needed when > 15 days remaining."""
        monitor = PatMonitor()

        # Set expiry date to 90 days in the future (well beyond 15-day buffer)
        expiry_date = datetime.now(timezone.utc) + timedelta(days=90)
        expiry_iso = expiry_date.isoformat()

        with patch.object(monitor, "_get_pat_expiry_from_secrets", return_value=expiry_iso):
            result = monitor.should_rotate()

            assert result is False

    def test_detects_no_rotation_needed_at_75_days_remaining(self):
        """Test that rotation is NOT needed at 75 days remaining (early in lifecycle)."""
        monitor = PatMonitor()

        # Set expiry date to 75 days in the future
        expiry_date = datetime.now(timezone.utc) + timedelta(days=75)
        expiry_iso = expiry_date.isoformat()

        with patch.object(monitor, "_get_pat_expiry_from_secrets", return_value=expiry_iso):
            result = monitor.should_rotate()

            # At 75 days remaining, rotation should NOT be needed (> 15 day buffer)
            assert result is False

    def test_detects_rotation_needed_at_exactly_15_day_boundary(self):
        """Test boundary condition at exactly 15 days."""
        monitor = PatMonitor()

        # Set expiry date to exactly 15 days in the future
        expiry_date = datetime.now(timezone.utc) + timedelta(days=15)
        expiry_iso = expiry_date.isoformat()

        with patch.object(monitor, "_get_pat_expiry_from_secrets", return_value=expiry_iso):
            result = monitor.should_rotate()

            # At exactly 15 days, rotation should be needed (days_remaining <= 15)
            assert result is True

    def test_detects_rotation_not_needed_at_20_days(self):
        """Test that rotation is NOT needed at 20 days (well above buffer)."""
        monitor = PatMonitor()

        # Set expiry date to 20 days in the future (well above 15-day buffer)
        expiry_date = datetime.now(timezone.utc) + timedelta(days=20)
        expiry_iso = expiry_date.isoformat()

        with patch.object(monitor, "_get_pat_expiry_from_secrets", return_value=expiry_iso):
            result = monitor.should_rotate()

            # At 20 days, rotation should NOT be needed (> 15 day buffer)
            assert result is False

    def test_detects_rotation_needed_when_already_expired(self):
        """Test that rotation is needed when PAT is already expired."""
        monitor = PatMonitor()

        # Set expiry date to 5 days in the past
        expiry_date = datetime.now(timezone.utc) - timedelta(days=5)
        expiry_iso = expiry_date.isoformat()

        with patch.object(monitor, "_get_pat_expiry_from_secrets", return_value=expiry_iso):
            result = monitor.should_rotate()

            assert result is True


class TestMissingPatExpiry:
    """Tests for handling missing JIRA_PAT_EXPIRY."""

    def test_handles_missing_pat_expiry_gracefully(self):
        """Test that missing JIRA_PAT_EXPIRY is handled gracefully."""
        monitor = PatMonitor()

        with patch.object(monitor, "_get_pat_expiry_from_secrets", return_value=None):
            result = monitor.should_rotate()

            # Should return True when expiry date is missing (force rotation)
            assert result is True

    def test_returns_none_days_remaining_when_expiry_missing(self):
        """Test that get_days_remaining returns None when expiry is missing."""
        monitor = PatMonitor()

        with patch.object(monitor, "_get_pat_expiry_from_secrets", return_value=None):
            days = monitor.get_days_remaining()

            assert days is None


class TestDateStringParsing:
    """Tests for parsing ISO 8601 date strings."""

    def test_parses_iso_8601_date_strings(self):
        """Test that ISO 8601 date strings are parsed correctly."""
        monitor = PatMonitor()

        # Create an ISO 8601 date string
        test_date = datetime.now(timezone.utc) + timedelta(days=30)
        iso_string = test_date.isoformat()

        days_remaining = monitor._calculate_days_remaining(iso_string)

        # Should be approximately 30 days
        assert 29 <= days_remaining <= 30

    def test_parses_iso_8601_with_timezone_info(self):
        """Test that ISO 8601 strings with timezone info are parsed."""
        monitor = PatMonitor()

        # Create an ISO 8601 date string with timezone
        test_date = datetime.now(timezone.utc) + timedelta(days=45)
        iso_string = test_date.isoformat() + "Z"

        days_remaining = monitor._calculate_days_remaining(iso_string)

        # Should be approximately 45 days
        assert 44 <= days_remaining <= 45

    def test_handles_invalid_date_format(self):
        """Test that invalid date formats raise appropriate errors."""
        monitor = PatMonitor()

        invalid_date = "not-a-valid-date"

        with pytest.raises((ValueError, TypeError)):
            monitor._calculate_days_remaining(invalid_date)


class TestSecretsManagerIntegration:
    """Tests for AWS Secrets Manager integration."""

    def test_reads_pat_expiry_from_secrets_manager(self):
        """Test that PAT_EXPIRY is read from AWS Secrets Manager."""
        monitor = PatMonitor()

        expiry_date = datetime.now(timezone.utc) + timedelta(days=60)
        expiry_iso = expiry_date.isoformat()

        with patch.object(
            monitor, "_get_pat_expiry_from_secrets", return_value=expiry_iso
        ) as mock_get:
            days = monitor.get_days_remaining()

            mock_get.assert_called_once()
            assert days is not None
            assert 59 <= days <= 60


class TestPublicApi:
    """Tests for public API methods."""

    def test_get_days_remaining_returns_correct_value(self):
        """Test that get_days_remaining returns correct value."""
        monitor = PatMonitor()

        expiry_date = datetime.now(timezone.utc) + timedelta(days=50)
        expiry_iso = expiry_date.isoformat()

        with patch.object(monitor, "_get_pat_expiry_from_secrets", return_value=expiry_iso):
            days = monitor.get_days_remaining()

            assert days is not None
            assert 49 <= days <= 50

    def test_should_rotate_returns_boolean(self):
        """Test that should_rotate returns a boolean value."""
        monitor = PatMonitor()

        expiry_date = datetime.now(timezone.utc) + timedelta(days=90)
        expiry_iso = expiry_date.isoformat()

        with patch.object(monitor, "_get_pat_expiry_from_secrets", return_value=expiry_iso):
            result = monitor.should_rotate()

            assert isinstance(result, bool)
