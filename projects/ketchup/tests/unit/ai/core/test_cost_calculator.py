"""
test_cost_calculator.py

Unit tests for packages.ai.cost_calculator.TokenTracker and get_token_tracker.

Covers:
- Token usage tracking and reset
- Cost calculation for various token counts
- Edge cases (zero tokens, large numbers)
- Singleton behavior of get_token_tracker
- All tests follow the Ketchup Slack Bot test plan and cursor rules
"""

import pytest

from packages.ai.cost_calculator import TokenTracker, get_token_tracker
from packages.core.constants import INPUT_COST_PER_MILLION, OUTPUT_COST_PER_MILLION


@pytest.mark.unit
class TestTokenTracker:
    """Unit tests for TokenTracker class in cost_calculator.py."""

    def setup_method(self) -> None:
        """Create a new TokenTracker for each test."""
        self.tracker = TokenTracker()

    def test_initial_state(self) -> None:
        """Test that a new TokenTracker starts with zeroed counters."""
        summary = self.tracker.get_usage_summary()
        assert summary["input_tokens"] == 0
        assert summary["output_tokens"] == 0
        assert summary["total_tokens"] == 0
        assert summary["request_count"] == 0
        assert summary["input_cost"] == 0.0
        assert summary["output_cost"] == 0.0
        assert summary["total_cost"] == 0.0

    def test_add_usage_and_summary(self) -> None:
        """Test adding token usage and getting correct summary and costs."""
        self.tracker.add_usage(1000, 2000)
        self.tracker.add_usage(500, 500)
        summary = self.tracker.get_usage_summary()
        assert summary["input_tokens"] == 1500
        assert summary["output_tokens"] == 2500
        assert summary["total_tokens"] == 4000
        assert summary["request_count"] == 2
        # Cost calculations
        expected_input_cost = round((1500 / 1_000_000) * INPUT_COST_PER_MILLION, 6)
        expected_output_cost = round((2500 / 1_000_000) * OUTPUT_COST_PER_MILLION, 6)
        expected_total_cost = round(expected_input_cost + expected_output_cost, 6)
        assert summary["input_cost"] == expected_input_cost
        assert summary["output_cost"] == expected_output_cost
        assert summary["total_cost"] == expected_total_cost

    @pytest.mark.parametrize(
        "input_tokens,output_tokens,expected_input_cost,expected_output_cost,expected_total_cost",
        [
            (0, 0, 0.0, 0.0, 0.0),
            (1_000_000, 0, INPUT_COST_PER_MILLION, 0.0, INPUT_COST_PER_MILLION),
            (0, 1_000_000, 0.0, OUTPUT_COST_PER_MILLION, OUTPUT_COST_PER_MILLION),
            (
                1_000_000,
                1_000_000,
                INPUT_COST_PER_MILLION,
                OUTPUT_COST_PER_MILLION,
                INPUT_COST_PER_MILLION + OUTPUT_COST_PER_MILLION,
            ),
            (
                10_000_000,
                5_000_000,
                10 * INPUT_COST_PER_MILLION,
                5 * OUTPUT_COST_PER_MILLION,
                10 * INPUT_COST_PER_MILLION + 5 * OUTPUT_COST_PER_MILLION,
            ),
        ],
    )
    def test_calculate_cost_various(
        self,
        input_tokens: int,
        output_tokens: int,
        expected_input_cost: float,
        expected_output_cost: float,
        expected_total_cost: float,
    ) -> None:
        """Test calculate_cost static method for various token counts and edge cases."""
        costs = TokenTracker.calculate_cost(input_tokens, output_tokens)
        assert costs["Input Cost"] == round(expected_input_cost, 6)
        assert costs["Output Cost"] == round(expected_output_cost, 6)
        assert costs["Total Cost"] == round(expected_total_cost, 6)

    def test_large_token_counts(self) -> None:
        """Test that very large token counts are handled correctly."""
        self.tracker.add_usage(1_000_000_000, 2_000_000_000)
        summary = self.tracker.get_usage_summary()
        assert summary["input_tokens"] == 1_000_000_000
        assert summary["output_tokens"] == 2_000_000_000
        assert summary["total_tokens"] == 3_000_000_000
        # Costs should be large but not overflow
        assert summary["input_cost"] == round(
            (1_000_000_000 / 1_000_000) * INPUT_COST_PER_MILLION, 6
        )
        assert summary["output_cost"] == round(
            (2_000_000_000 / 1_000_000) * OUTPUT_COST_PER_MILLION, 6
        )

    def test_get_usage_summary(self) -> None:
        """Test get_usage_summary returns correct dictionary with costs."""
        summary = self.tracker.get_usage_summary()
        assert summary["input_tokens"] == 0
        assert summary["output_tokens"] == 0
        assert summary["total_tokens"] == 0
        assert summary["request_count"] == 0
        assert summary["input_cost"] == 0.0
        assert summary["output_cost"] == 0.0
        assert summary["total_cost"] == 0.0


@pytest.mark.unit
def test_get_token_tracker_singleton() -> None:
    """Test that get_token_tracker returns the same singleton instance."""
    tracker1 = get_token_tracker()
    tracker2 = get_token_tracker()
    assert tracker1 is tracker2
    # Changing one should affect the other
    tracker1.add_usage(10, 20)
    assert tracker2.get_usage_summary()["input_tokens"] == 10
    assert tracker2.get_usage_summary()["output_tokens"] == 20
