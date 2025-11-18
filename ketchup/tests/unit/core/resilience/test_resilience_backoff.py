"""
test_resilience_backoff.py

Unit tests for ExponentialBackoffStrategy and with_exponential_backoff in packages.core.resilience.backoff.

Covers:
- Success and failure retry logic
- Decorator usage for async functions
- Error handling and retry count edge cases

All tests follow the Ketchup Slack Bot test plan and cursor rules.
"""

import asyncio

import pytest

from packages.core.resilience.backoff import (
    ExponentialBackoffStrategy,
    with_exponential_backoff,
)

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
@pytest.mark.unit
async def test_exponential_backoff_success() -> None:
    """Test that ExponentialBackoffStrategy returns result on first try.

    Ensures that a successful function is not retried and returns the correct result.
    """
    strat = ExponentialBackoffStrategy(max_retries=2, base_delay=0.01, max_delay=0.05)

    async def succeed() -> int:
        return 42

    result = await strat.execute(succeed)
    assert result == 42


@pytest.mark.asyncio
@pytest.mark.unit
async def test_exponential_backoff_retries_and_fails() -> None:
    """Test that ExponentialBackoffStrategy retries and raises after max retries.

    Ensures that a retryable error is retried the correct number of times and then raised.
    """
    strat = ExponentialBackoffStrategy(max_retries=2, base_delay=0.01, max_delay=0.05)
    calls = []

    async def fail() -> None:
        calls.append(1)
        raise asyncio.TimeoutError("timeout")

    with pytest.raises(asyncio.TimeoutError):
        await strat.execute(fail)
    assert len(calls) == 3  # initial + 2 retries


@pytest.mark.asyncio
@pytest.mark.unit
async def test_with_exponential_backoff_decorator_success() -> None:
    """Test the with_exponential_backoff decorator on a successful function.

    Ensures that the decorator does not retry on success and returns the correct result.
    """

    @with_exponential_backoff(max_retries=1, base_delay=0.01, max_delay=0.05)
    async def foo() -> str:
        return "ok"

    assert await foo() == "ok"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_with_exponential_backoff_decorator_retries() -> None:
    """Test the with_exponential_backoff decorator retries and raises.

    Ensures that the decorator retries the correct number of times and raises the error.
    """
    calls = []

    @with_exponential_backoff(max_retries=1, base_delay=0.01, max_delay=0.05)
    async def bar() -> None:
        calls.append(1)
        raise asyncio.TimeoutError("timeout")

    with pytest.raises(asyncio.TimeoutError):
        await bar()
    assert len(calls) == 2
