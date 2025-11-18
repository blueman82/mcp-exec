"""
time_utils.py

This module contains utility functions for working with time and dates.
"""

from datetime import datetime, timedelta, timezone

from packages.core.logging import setup_logger

logger = setup_logger(__name__)


def convert_timestamp_to_utc(timestamp):
    """
    Convert a Unix timestamp to a human-readable UTC string.

    This function converts the given Unix timestamp (seconds since the epoch) to a UTC
    datetime object and then formats it as a string in the format "HH:MM:SS, dd-Mmm-YYYY".

    Args:
        timestamp: The Unix timestamp to convert.

    Returns:
        A string representing the UTC time in a human-readable format.
    """
    if not timestamp:
        return "N/A"

    try:
        # Convert the timestamp to a UTC datetime object
        utc_time = datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
        # Format the datetime object to a string and return it
        return utc_time.strftime("%H:%M:%S, %d-%b-%Y")
    except Exception as e:
        logger.error("Error converting timestamp %s to UTC: %s", timestamp, str(e))
        return "Invalid Timestamp"


def convert_days_to_epoch(number_of_days):
    """
    Convert a number of days into an epoch timestamp.

    For example, if number_of_days is 30, this returns the epoch time for 30 days ago from now.

    Args:
        number_of_days: Number of days to subtract from current time

    Returns:
        Epoch timestamp (int) representing the specified time in the past
    """
    threshold_time = datetime.now(timezone.utc) - timedelta(days=number_of_days)
    return int(threshold_time.timestamp())
