"""
Time period validation logic for metrics command.

Validates historical limits, future dates, and period constraints.
"""

from datetime import datetime, timezone
from typing import Tuple


def validate_historical_limit(year: int) -> Tuple[bool, str]:
    """
    Validate that requested year is within historical limits.
    
    Rules:
    - Current year: allowed
    - Previous year: allowed
    - 2+ years ago: rejected
    
    Args:
        year: Requested year (4-digit)
        
    Returns:
        Tuple of (is_valid, error_message)
        
    Examples:
        If current year is 2025:
        - validate_historical_limit(2025) → (True, "")
        - validate_historical_limit(2024) → (True, "")
        - validate_historical_limit(2023) → (False, "error message")
    """
    current_year = datetime.now(timezone.utc).year
    min_allowed_year = current_year - 1
    
    if year < min_allowed_year:
        error_msg = (
            f"❌ Metrics only available for current year and previous year.\n"
            f"You requested: {year}\n"
            f"Available: {min_allowed_year}-{current_year}"
        )
        return False, error_msg
    
    return True, ""


def validate_not_future(end_date: datetime) -> Tuple[bool, str]:
    """
    Validate that the end date is not in the future.
    
    Args:
        end_date: End datetime of requested period
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    now = datetime.now(timezone.utc)
    
    if end_date > now:
        # Format the date for error message
        month_name = end_date.strftime("%B")
        year = end_date.year
        
        error_msg = (
            f"❌ Cannot generate metrics for future time periods.\n"
            f"{month_name} {year} hasn't occurred yet."
        )
        return False, error_msg
    
    return True, ""


def validate_time_period(year: int, end_date: datetime) -> Tuple[bool, str]:
    """
    Run all validations on a time period.
    
    Args:
        year: Requested year
        end_date: End datetime of period
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check historical limit
    is_valid, error_msg = validate_historical_limit(year)
    if not is_valid:
        return False, error_msg
    
    # Check not future
    is_valid, error_msg = validate_not_future(end_date)
    if not is_valid:
        return False, error_msg
    
    return True, ""
