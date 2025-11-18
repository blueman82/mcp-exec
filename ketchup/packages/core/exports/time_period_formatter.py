"""
Time period formatting utilities for dashboard display.

Generates human-readable labels and date ranges for display.
"""

from datetime import datetime


def format_time_period_label(
    period_type: str,
    month: int = None,
    quarter: int = None,
    year: int = None,
) -> str:
    """
    Generate concise label for dashboard title.
    
    Args:
        period_type: "7_days", "monthly", or "quarterly"
        month: Month number (1-12) for monthly
        quarter: Quarter number (1-4) for quarterly
        year: 4-digit year
        
    Returns:
        Label string for display
        
    Examples:
        ("7_days", ...) → "Past 7 days"
        ("monthly", 9, None, 2025) → "September 2025"
        ("quarterly", None, 1, 2025) → "Q1 2025"
    """
    if period_type == "7_days":
        return "Past 7 days"
    
    elif period_type == "monthly":
        month_name = datetime(year, month, 1).strftime("%B")
        return f"{month_name} {year}"
    
    elif period_type == "quarterly":
        return f"Q{quarter} {year}"
    
    return "Unknown Period"


def format_time_period_full(
    period_type: str,
    month: int = None,
    quarter: int = None,
    year: int = None,
    is_partial: bool = False,
) -> str:
    """
    Generate full period description with partial indicator.
    
    Args:
        period_type: "7_days", "monthly", or "quarterly"
        month: Month number for monthly
        quarter: Quarter number for quarterly
        year: 4-digit year
        is_partial: True if ongoing/incomplete period
        
    Returns:
        Full description string
        
    Examples:
        ("monthly", 9, None, 2025, False) → "September 2025"
        ("monthly", 10, None, 2025, True) → "October 2025 (partial)"
        ("quarterly", None, 1, 2025, False) → "Q1 2025"
    """
    label = format_time_period_label(period_type, month, quarter, year)
    
    if is_partial:
        return f"{label} (partial)"
    
    return label


def format_date_range(start_date: datetime, end_date: datetime) -> str:
    """
    Format date range for display.
    
    Args:
        start_date: Start datetime
        end_date: End datetime
        
    Returns:
        Formatted date range string
        
    Examples:
        (2025-09-01, 2025-09-30) → "Sept 1 - Sept 30, 2025"
        (2024-12-01, 2025-02-28) → "Dec 1, 2024 - Feb 28, 2025"
    """
    def format_month(dt: datetime) -> str:
        """Format month name with 'Sept' special case."""
        month = dt.strftime('%b')
        if month == 'Sep':
            return 'Sept'
        return month
    
    # Same year
    if start_date.year == end_date.year:
        # Same month
        if start_date.month == end_date.month:
            return (
                f"{format_month(start_date)} {start_date.day} - "
                f"{format_month(end_date)} {end_date.day}, {end_date.year}"
            )
        else:
            # Different months, same year
            return (
                f"{format_month(start_date)} {start_date.day} - "
                f"{format_month(end_date)} {end_date.day}, {end_date.year}"
            )
    else:
        # Different years
        return (
            f"{format_month(start_date)} {start_date.day}, {start_date.year} - "
            f"{format_month(end_date)} {end_date.day}, {end_date.year}"
        )


def format_confirmation_message(
    period_type: str,
    month: int = None,
    quarter: int = None,
    year: int = None,
    is_partial: bool = False,
    start_date: datetime = None,
    end_date: datetime = None,
) -> str:
    """
    Generate confirmation message to send before dashboard generation.
    
    Args:
        period_type: Time period type
        month: Month number
        quarter: Quarter number
        year: Year
        is_partial: Is ongoing period
        start_date: Start datetime
        end_date: End datetime
        
    Returns:
        Formatted confirmation message
        
    Examples:
        "📊 Generating dashboard for: **Past 7 days** (Oct 3 - Oct 10, 2025)"
        "📊 Generating dashboard for: **September 2025** (Sept 1 - Sept 30, 2025)"
        "📊 Generating dashboard for: **Q1 2025** (Dec 1, 2024 - Feb 28, 2025)"
    """
    period_full = format_time_period_full(period_type, month, quarter, year, is_partial)
    date_range = format_date_range(start_date, end_date)
    
    return f"📊 Generating dashboard for: **{period_full}** ({date_range})"


def get_month_keys_for_range(start_date: datetime, end_date: datetime) -> list:
    """
    Get list of month keys (YYYY_MM format) for a date range.
    
    Args:
        start_date: Start datetime
        end_date: End datetime
        
    Returns:
        List of month keys in format YYYY_MM
        
    Examples:
        Q1 2025 (Dec 2024 - Feb 2025) → 
        ["2024_12", "2025_01", "2025_02"]
    """
    keys = []
    current = start_date.replace(day=1)
    
    while current <= end_date:
        keys.append(current.strftime("%Y_%m"))
        
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    
    return keys
