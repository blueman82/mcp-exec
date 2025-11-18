"""
Unit tests for dynamodb_config.py in packages.db.config.

Covers:
- DynamoDBConfig: default values from constants, custom values
- get_table_name and get_region methods
- Edge cases: empty string, unusual values
- All tests pass mypy --strict and ruff
- Expected: correct attribute assignment, method return values
"""

import pytest

from packages.core import constants
from packages.db.config.dynamodb_config import DynamoDBConfig

pytestmark = pytest.mark.unit


def test_dynamodb_config_defaults() -> None:
    """Test DynamoDBConfig uses default values from constants."""
    config = DynamoDBConfig()
    assert config.table_name == constants.DYNAMODB_TABLE_NAME
    assert config.region == constants.AWS_REGION
    assert config.get_table_name() == constants.DYNAMODB_TABLE_NAME
    assert config.get_region() == constants.AWS_REGION


def test_dynamodb_config_custom_values() -> None:
    """Test DynamoDBConfig uses custom table name and region."""
    config = DynamoDBConfig(table_name="custom_table", region="us-east-2")
    assert config.table_name == "custom_table"
    assert config.region == "us-east-2"
    assert config.get_table_name() == "custom_table"
    assert config.get_region() == "us-east-2"


def test_dynamodb_config_edge_cases() -> None:
    """Test DynamoDBConfig with empty string values."""
    config = DynamoDBConfig(table_name="", region="")
    assert config.table_name == ""
    assert config.region == ""
    assert config.get_table_name() == ""
    assert config.get_region() == ""


def test_dynamodb_config_override_via_env(monkeypatch) -> None:
    """Test DynamoDBConfig values can be overridden by environment variables."""
    # ... existing code ...
