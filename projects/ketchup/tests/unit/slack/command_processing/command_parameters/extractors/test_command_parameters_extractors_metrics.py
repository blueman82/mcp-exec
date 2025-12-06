"""Unit tests for metrics parameter extraction."""

from datetime import datetime, timezone

import pytest

from packages.slack.command_processing.command_parameters.extractors.metrics import (
    extract_metrics_params,
)
from packages.slack.command_processing.command_parameters.models import CommandContext
from packages.slack.command_processing.command_parameters.validation import ValidationError


class TestExtractMetricsParams:
    """Test metrics parameter extraction."""

    def test_default_7_days(self) -> None:
        """Test default 7-day mode."""
        params = extract_metrics_params("/ketchup metrics", CommandContext.DIRECT_MESSAGE)
        assert params.time_period_type == "7_days"
        assert params.month is None
        assert params.quarter is None
        assert params.is_partial is False

    def test_monthly_full_name(self) -> None:
        """Test monthly with full month name."""
        current_year = datetime.now(timezone.utc).year
        params = extract_metrics_params(
            f"/ketchup metrics september {current_year}", CommandContext.DIRECT_MESSAGE
        )
        assert params.time_period_type == "monthly"
        assert params.month == 9
        assert params.year == current_year

    def test_monthly_abbreviated(self) -> None:
        """Test monthly with abbreviated month."""
        current_year = datetime.now(timezone.utc).year
        params = extract_metrics_params(
            f"/ketchup metrics sept {current_year}", CommandContext.DIRECT_MESSAGE
        )
        assert params.time_period_type == "monthly"
        assert params.month == 9

    def test_quarterly(self) -> None:
        """Test quarterly mode."""
        current_year = datetime.now(timezone.utc).year
        params = extract_metrics_params(
            f"/ketchup metrics q1 {current_year}", CommandContext.DIRECT_MESSAGE
        )
        assert params.time_period_type == "quarterly"
        assert params.quarter == 1
        assert params.year == current_year

    def test_two_digit_year(self) -> None:
        """Test 2-digit year conversion."""
        params = extract_metrics_params("/ketchup metrics sept 25", CommandContext.DIRECT_MESSAGE)
        assert params.year == 2025

    def test_invalid_month_name(self) -> None:
        """Test invalid month name raises error."""
        with pytest.raises(ValidationError) as exc:
            extract_metrics_params("/ketchup metrics xyz 25", CommandContext.DIRECT_MESSAGE)
        assert "Invalid time period" in str(exc.value.user_message)

    def test_invalid_quarter(self) -> None:
        """Test invalid quarter raises error."""
        with pytest.raises(ValidationError) as exc:
            extract_metrics_params("/ketchup metrics q5 25", CommandContext.DIRECT_MESSAGE)
        assert "Invalid time period" in str(exc.value.user_message)

    def test_too_many_args(self) -> None:
        """Test too many arguments raises error."""
        with pytest.raises(ValidationError) as exc:
            extract_metrics_params("/ketchup metrics sept 25 extra", CommandContext.DIRECT_MESSAGE)
        assert "Invalid time period format" in str(exc.value.user_message)

    def test_missing_year(self) -> None:
        """Test missing year raises error."""
        with pytest.raises(ValidationError) as exc:
            extract_metrics_params("/ketchup metrics september", CommandContext.DIRECT_MESSAGE)
        assert "Invalid time period format" in str(exc.value.user_message)

    def test_public_channel_rejected(self) -> None:
        """Test public channel usage is rejected."""
        with pytest.raises(ValidationError) as exc:
            extract_metrics_params("/ketchup metrics", CommandContext.PUBLIC_CHANNEL)
        assert "only available in direct messages" in str(exc.value.user_message)
