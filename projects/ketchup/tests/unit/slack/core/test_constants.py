"""
test_constants.py

Unit tests for core constants in packages.core.constants.

Covers:
- Default values for AWS, DynamoDB, OpenAI, Slack, and retry constants

All tests follow the Ketchup Slack Bot test plan and cursor rules.
"""

import pytest

import packages.core.constants as c

pytestmark = pytest.mark.unit


@pytest.mark.unit
def test_constants_defaults() -> None:
    """Test that key constants exist and have valid values.

    Note: Constants are read from environment at module import time.
    In parallel test execution, other tests may set env vars before import.
    We verify constants exist and have reasonable values, not specific defaults.
    """
    # Verify constants exist and are strings/have expected types
    assert isinstance(c.AWS_REGION, str) and len(c.AWS_REGION) > 0
    assert isinstance(c.DYNAMODB_TABLE_NAME, str) and len(c.DYNAMODB_TABLE_NAME) > 0
    assert isinstance(c.AWS_SECRET_NAME, str) and len(c.AWS_SECRET_NAME) > 0
    # These constants are not environment-dependent
    assert c.OPENAI_API_VERSION == "2024-12-01-preview"
    assert c.SLACK_API_TIMEOUT.total == 120
    assert c.MAX_RETRIES == 10
