"""
Time period parsing utilities for metrics command.

Handles parsing of month names, quarters, and year specifications.
"""

import calendar
from datetime import datetime, timezone
from typing import Optional, Tuple

# Month name mapping (3+ character abbreviations, case-insensitive)
MONTH_NAMES = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

# Custom fiscal quarter mapping
QUARTER_MONTHS = {
    1: [12, 1, 2],  # Q1 = Dec, Jan, Feb
    2: [3, 4, 5],  # Q2 = Mar, Apr, May
    3: [6, 7, 8],  # Q3 = Jun, Jul, Aug
    4: [9, 10, 11],  # Q4 = Sept, Oct, Nov
}


def parse_month_name(month_str: str) -> Optional[int]:
    """
    Parse month name to month number (1-12).

    Args:
        month_str: Month name (case-insensitive, 3+ chars)

    Returns:
        Month number (1-12) or None if not recognized

    Examples:
        "september" → 9
        "sept" → 9
        "sep" → 9
        "se" → None (too short)
    """
    month_lower = month_str.lower()

    # Check if it's at least 3 characters
    if len(month_lower) < 3:
        return None

    # Check full name first
    if month_lower in MONTH_NAMES:
        return MONTH_NAMES[month_lower]

    # Check if it's a valid prefix (3+ chars)
    matches = [
        num
        for name, num in MONTH_NAMES.items()
        if name.startswith(month_lower) and len(month_lower) >= 3
    ]

    # Return match if unambiguous
    if len(matches) == 1:
        return matches[0]

    return None


def parse_quarter(quarter_str: str) -> Optional[int]:
    """
    Parse quarter string to quarter number (1-4).

    Args:
        quarter_str: Quarter string (e.g., "q1", "Q2")

    Returns:
        Quarter number (1-4) or None if invalid

    Examples:
        "q1" → 1
        "Q4" → 4
        "q5" → None
    """
    quarter_lower = quarter_str.lower()

    if not quarter_lower.startswith("q"):
        return None

    try:
        quarter_num = int(quarter_lower[1:])
        if 1 <= quarter_num <= 4:
            return quarter_num
    except (ValueError, IndexError):
        pass

    return None


def parse_year(year_str: str) -> Optional[int]:
    """
    Parse year string to 4-digit year.

    Args:
        year_str: Year string (2-digit or 4-digit)

    Returns:
        4-digit year or None if invalid

    Examples:
        "25" → 2025
        "2025" → 2025
        "99" → 2099
    """
    try:
        year = int(year_str)

        # 2-digit year: convert to 20xx
        if year < 100:
            return 2000 + year

        # 4-digit year: use as-is
        if 2000 <= year <= 2100:
            return year

    except ValueError:
        pass

    return None


def get_month_start_end(year: int, month: int) -> Tuple[datetime, datetime]:
    """
    Get start and end datetime for a given month.

    Args:
        year: 4-digit year
        month: Month number (1-12)

    Returns:
        Tuple of (start_datetime, end_datetime) in UTC

    Examples:
        get_month_start_end(2025, 9) →
        (2025-09-01 00:00:00 UTC, 2025-09-30 23:59:59 UTC)
    """
    # First day of month at midnight
    start = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)

    # Last day of month at 23:59:59
    days_in_month = calendar.monthrange(year, month)[1]
    end = datetime(year, month, days_in_month, 23, 59, 59, tzinfo=timezone.utc)

    return start, end


def get_quarter_start_end(year: int, quarter: int) -> Tuple[datetime, datetime]:
    """
    Get start and end datetime for a given quarter.

    Uses custom fiscal quarters:
    Q1 = Dec (prev year), Jan, Feb
    Q2 = Mar, Apr, May
    Q3 = Jun, Jul, Aug
    Q4 = Sept, Oct, Nov

    Args:
        year: 4-digit year (year the quarter ends in)
        quarter: Quarter number (1-4)

    Returns:
        Tuple of (start_datetime, end_datetime) in UTC

    Examples:
        get_quarter_start_end(2025, 1) →
        (2024-12-01 00:00:00 UTC, 2025-02-28 23:59:59 UTC)
    """
    months = QUARTER_MONTHS[quarter]

    # Handle Q1 special case (December is in previous year)
    if quarter == 1:
        start_year = year - 1
        start_month = 12
        end_year = year
        end_month = 2
    else:
        start_year = year
        start_month = months[0]
        end_year = year
        end_month = months[-1]

    # Start: First day of first month
    start = datetime(start_year, start_month, 1, 0, 0, 0, tzinfo=timezone.utc)

    # End: Last day of last month
    days_in_end_month = calendar.monthrange(end_year, end_month)[1]
    end = datetime(end_year, end_month, days_in_end_month, 23, 59, 59, tzinfo=timezone.utc)

    return start, end


def is_ongoing_period(start: datetime, end: datetime) -> bool:
    """
    Check if a time period is ongoing (current time falls within it).

    Args:
        start: Period start datetime
        end: Period end datetime

    Returns:
        True if current time is within period
    """
    now = datetime.now(timezone.utc)
    return start <= now <= end


def get_month_keys_for_range(start: datetime, end: datetime) -> list[str]:
    """
    Get list of month keys (YYYY_MM format) for a date range.

    Args:
        start: Start datetime
        end: End datetime

    Returns:
        List of month keys in format YYYY_MM

    Examples:
        Q1 2025 (Dec 2024 - Feb 2025) →
        ["2024_12", "2025_01", "2025_02"]
    """
    keys = []
    current = start.replace(day=1)

    while current <= end:
        keys.append(current.strftime("%Y_%m"))

        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    return keys
