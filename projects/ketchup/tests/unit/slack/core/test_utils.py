"""
test_utils.py

Unit tests for parse_slack_body in packages.core.event_parsing_utils.

Covers:
- JSON, form-urlencoded, missing body, and Slack payload edge cases
- Error handling for invalid input

All tests follow the Ketchup Slack Bot test plan and cursor rules.
"""

import json

import pytest

from packages.core.event_parsing_utils import parse_slack_body

pytestmark = pytest.mark.unit


@pytest.mark.unit
class TestParseSlackBody:
    """Unit tests for parse_slack_body utility function.

    Tests parsing raw request bodies directly from FastAPI without Lambda wrapping.
    """

    def test_json_body(self) -> None:
        """Test parsing a standard JSON body."""
        raw = b'{"foo": "bar", "baz": 123}'
        single, multi = parse_slack_body(raw, "application/json")
        assert single == {"foo": "bar", "baz": 123}
        assert multi == {"foo": ["bar"], "baz": [123]}

    def test_form_urlencoded_body(self) -> None:
        """Test parsing a form-urlencoded body."""
        raw = b"foo=bar&baz=123"
        single, multi = parse_slack_body(raw, "application/x-www-form-urlencoded")
        assert single == {"foo": "bar", "baz": "123"}
        assert multi == {"foo": ["bar"], "baz": ["123"]}

    def test_missing_body(self) -> None:
        """Test raw body that is empty returns empty dicts."""
        single, multi = parse_slack_body(b"", "application/json")
        assert single == {}
        assert multi == {}

    def test_slack_payload_nested_json(self) -> None:
        """Test Slack payload with nested JSON in form-urlencoded body."""
        payload = {"type": "block_actions", "user": {"id": "U123"}}
        raw = f"payload={json.dumps(payload)}".encode()
        single, multi = parse_slack_body(raw, "application/x-www-form-urlencoded")
        assert "payload" in single
        assert isinstance(single["payload"], dict)
        assert single["payload"]["type"] == "block_actions"
        assert single["payload"]["user"]["id"] == "U123"

    def test_invalid_json_body(self) -> None:
        """Test raw body with invalid JSON returns empty dicts."""
        raw = b"{invalid json}"
        single, multi = parse_slack_body(raw, "application/json")
        assert single == {}
        assert multi == {}
