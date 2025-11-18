"""
cost_calculator.py

Utilities for tracking and calculating OpenAI API costs.
"""

from typing import Any, Dict

from packages.core.constants import INPUT_COST_PER_MILLION, OUTPUT_COST_PER_MILLION


class TokenTracker:
    """
    A class to track token usage and associated costs.
    """

    def __init__(self) -> None:
        """Initialize the token tracker."""
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.total_tokens: int = 0
        self.request_count: int = 0

    @staticmethod
    def calculate_cost(input_tokens: int, output_tokens: int) -> Dict[str, float]:
        """
        Calculate the cost of an OpenAI API request based on token usage.

        Args:
            input_tokens: Number of tokens in the input request
            output_tokens: Number of tokens in the output response

        Returns:
            Dictionary containing input cost, output cost, and total cost
        """
        input_cost = (input_tokens / 1_000_000) * INPUT_COST_PER_MILLION
        output_cost = (output_tokens / 1_000_000) * OUTPUT_COST_PER_MILLION
        total_cost = input_cost + output_cost

        return {
            "Input Cost": round(input_cost, 6),
            "Output Cost": round(output_cost, 6),
            "Total Cost": round(total_cost, 6),
        }

    def add_usage(self, input_tokens: int, output_tokens: int) -> None:
        """
        Add token usage from a request.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        """
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += input_tokens + output_tokens
        self.request_count += 1

    def get_usage_summary(self) -> Dict[str, Any]:
        """
        Get a summary of token usage and costs.

        Returns:
            Dictionary with usage statistics
        """
        # Calculate costs using the static method
        costs = self.calculate_cost(self.input_tokens, self.output_tokens)

        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "request_count": self.request_count,
            "input_cost": costs["Input Cost"],
            "output_cost": costs["Output Cost"],
            "total_cost": costs["Total Cost"],
        }


# Singleton token tracker instance
_token_tracker = TokenTracker()


def get_token_tracker() -> TokenTracker:
    """
    Get the singleton token tracker instance.

    Returns:
        The token tracker instance
    """
    return _token_tracker
