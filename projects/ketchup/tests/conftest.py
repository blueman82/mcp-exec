import asyncio
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add the project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# Import all AWS mocking fixtures to make them available to all tests
from packages.core.testing.aws_mocks import *  # noqa: F401,F403

# Load AWS configuration from .env.test (optional)
# Each developer can use their own AWS profile without committing to git
env_test = Path(__file__).parent.parent / ".env.test"
if env_test.exists():
    with open(env_test) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

# Set defaults if not loaded from .env.test
os.environ.setdefault("AWS_PROFILE", "campaign_prod_v7")
os.environ.setdefault("AWS_REGION", "eu-west-1")


def _reset_mock_recursive(obj: Any) -> None:
    """Recursively reset all mock objects in a given object."""
    if isinstance(obj, (AsyncMock, MagicMock)):
        obj.reset_mock(side_effect=True, return_value=True)
    elif isinstance(obj, dict):
        for value in obj.values():
            _reset_mock_recursive(value)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _reset_mock_recursive(item)


@pytest.fixture(autouse=True)
def reset_all_mocks(request: pytest.FixtureRequest) -> None:
    """
    Automatically reset all AsyncMock and MagicMock instances after each test.

    This fixture ensures no mock state persists between tests, preventing
    test pollution from shared mock call history, return values, or side_effects.

    Runs after each test via yield + cleanup pattern.
    """
    yield  # Test runs

    # Reset all mocks in all fixtures after test completes
    for fixture_name in request.fixturenames:
        try:
            fixture_value = request.getfixturevalue(fixture_name)
            _reset_mock_recursive(fixture_value)
        except Exception:
            # Skip fixtures that can't be resolved or don't need reset
            pass


@pytest.fixture(autouse=True)
def cleanup_async_resources() -> None:
    """
    Clean up async resources and pending tasks after each test.

    Ensures event loop is clean for next test, preventing async state pollution.
    """
    yield  # Test runs

    # Cancel any pending tasks to prevent event loop pollution
    try:
        pending = asyncio.all_tasks()
        for task in pending:
            task.cancel()
    except RuntimeError:
        # Event loop may be closed or not available
        pass
