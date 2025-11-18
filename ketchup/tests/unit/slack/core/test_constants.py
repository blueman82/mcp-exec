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
    """Test that key constants have expected default values.

    Ensures that environment and functional constants are set as expected for dev/test environments.
    """
    assert c.AWS_REGION == "eu-west-1"
    assert c.DYNAMODB_TABLE_NAME == "ketchup_channel_information"
    assert c.AWS_SECRET_NAME == "Ketchup_Token_Secrets"
    assert c.OPENAI_API_VERSION == "2025-01-01-preview"
    assert c.SLACK_API_TIMEOUT.total == 120
    assert c.MAX_RETRIES == 10
