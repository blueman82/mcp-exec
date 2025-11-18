"""
test_time_utils.py

Unit tests for time utility functions in packages.core.time_utils.

Covers:
- convert_timestamp_to_utc: Valid, None, and invalid input cases
- convert_days_to_epoch: Correctness of epoch calculation

All tests follow the Ketchup Slack Bot test plan and cursor rules.
"""

import time

import pytest

from packages.core.time_utils import convert_days_to_epoch, convert_timestamp_to_utc

pytestmark = pytest.mark.unit


@pytest.mark.unit
def test_convert_timestamp_to_utc_valid() -> None:
    """Test converting a valid Unix timestamp to UTC string.

    Verifies correct formatting and expected date output.
    """
    ts = 1609459200  # 2021-01-01 00:00:00 UTC
    result = convert_timestamp_to_utc(ts)  # type: ignore[no-untyped-call]
    assert result.endswith("01-Jan-2021")
    assert ":" in result


@pytest.mark.unit
def test_convert_timestamp_to_utc_none() -> None:
    """Test converting None returns 'N/A'.

    Ensures that None input is handled gracefully.
    """
    assert convert_timestamp_to_utc(None) == "N/A"  # type: ignore[no-untyped-call]


@pytest.mark.unit
def test_convert_timestamp_to_utc_invalid() -> None:
    """Test converting an invalid timestamp returns 'Invalid Timestamp'.

    Ensures that invalid input does not raise and returns a clear error string.
    """
    assert convert_timestamp_to_utc("not-a-timestamp").startswith("Invalid")  # type: ignore[no-untyped-call]


@pytest.mark.unit
def test_convert_days_to_epoch() -> None:
    """Test converting days to epoch returns a timestamp in the past.

    Checks that the returned epoch is within the expected range for the given days.
    """
    now = int(time.time())
    days = 5
    epoch = convert_days_to_epoch(days)  # type: ignore[no-untyped-call]
    # Should be between 4 and 6 days ago (allowing for test timing)
    assert now - epoch >= 4 * 24 * 3600
    assert now - epoch <= 6 * 24 * 3600
