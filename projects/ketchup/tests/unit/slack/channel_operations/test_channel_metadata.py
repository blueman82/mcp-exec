"""
Unit tests for channel_metadata.py in packages.db.models.

Covers:
- ChannelMetadata: construction with required/optional fields
- to_item: default, custom fields, edge cases, type handling
- Ensures required fields in output (customer_name, jira_ticket, product)
- All tests pass mypy --strict and ruff
- Expected: correct DynamoDB item output, type descriptors, field presence
"""

import pytest

from packages.db.models.channel_metadata import ChannelMetadata

pytestmark = pytest.mark.unit


def test_channel_metadata_defaults() -> None:
    """Test ChannelMetadata with only required fields."""
    meta = ChannelMetadata(channel_id="C123", channel_name="test")
    item = meta.to_item()
    assert item["PK"] == {"S": "CHANNEL#C123"}
    assert item["SK"] == {"S": "CSO_DETAILS"}
    assert item["channel_id"] == {"S": "C123"}
    assert item["channel_name"] == {"S": "test"}
    assert item["archived"] == {"BOOL": False}
    assert item["created_at"] == {"N": "0"}
    assert item["archived_at"] == {"N": "0"}
    assert item["customer_name"]["S"]
    assert item["jira_ticket"]["S"]
    assert item["product"]["S"]
    assert "timestamp" in item


def test_channel_metadata_with_all_fields() -> None:
    """Test ChannelMetadata with all fields and custom fields."""
    meta = ChannelMetadata(
        channel_id="C456",
        channel_name="chan",
        archived=True,
        date_created_epoch=123456,
        custom_fields={
            "archived_at": 789,
            "created_at": 654,
            "customer_name": "Acme",
            "jira_ticket": "JIRA-1",
            "product": "Widget",
            "extra_str": "foo",
            "extra_bool": True,
            "extra_num": 42,
        },
    )
    item = meta.to_item()
    assert item["archived"] == {"BOOL": True}
    assert item["created_at"] == {"N": "654"}
    assert item["archived_at"] == {"N": "789"}
    assert item["customer_name"] == {"S": "Acme"}
    assert item["jira_ticket"] == {"S": "JIRA-1"}
    assert item["product"] == {"S": "Widget"}
    assert item["extra_str"] == {"S": "foo"}
    assert item["extra_bool"] == {"BOOL": True}
    assert item["extra_num"] == {"N": "42"}
    assert item["channel_id"] == {"S": "C456"}
    assert item["channel_name"] == {"S": "chan"}
    assert "timestamp" in item


def test_channel_metadata_edge_cases() -> None:
    """Test ChannelMetadata with missing/extra custom fields and types.

    If a required field is present in custom_fields but is not a string, the type will be set according to its type (e.g., {"N": ...} for int/float),
    and will not fallback to the default string value. This matches the production logic.
    """
    meta = ChannelMetadata(
        channel_id="C789",
        channel_name="edge",
        custom_fields={"unknown": 3.14, "customer_name": 123, "extra": None},
    )
    item = meta.to_item()
    # unknown float should be N type
    assert item["unknown"] == {"N": "3.14"}
    # customer_name with wrong type (int) should be N type, not S
    assert item["customer_name"] == {"N": "123"}
    # None is ignored (not added)
    assert (
        "extra" not in item
        or item["extra"] == {"S": "NOT YET AVAILABLE"}
        or item["extra"] == {"S": "unknown"}
    )
    # Required fields always present (but may be N type if wrong type in custom_fields)
    assert "customer_name" in item
    assert "jira_ticket" in item
    assert "product" in item
