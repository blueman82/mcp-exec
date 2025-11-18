"""
test_utils.py

Unit tests for the parse_event_body utility function in packages.core.utils.

Covers:
- JSON, form-urlencoded, base64, missing body, and Slack payload edge cases
- Error handling for invalid input types

All tests follow the Ketchup Slack Bot test plan and cursor rules.
"""

import base64
import json

import pytest

from packages.core.event_parsing_utils import parse_event_body

pytestmark = pytest.mark.unit


@pytest.mark.unit
class TestParseEventBody:
    """Unit tests for parse_event_body utility function.

    Each test covers a specific input type or edge case for Lambda event parsing.
    """

    def test_json_body(self) -> None:
        """Test parsing a standard JSON body.

        Verifies that a JSON body is correctly parsed into single and multi-value dicts.
        """
        event = {
            "headers": {"content-type": "application/json"},
            "body": '{"foo": "bar", "baz": 123}',
        }
        raw, single, multi = parse_event_body(event)
        assert raw == b'{"foo": "bar", "baz": 123}'
        assert single == {"foo": "bar", "baz": 123}
        assert multi == {"foo": ["bar"], "baz": [123]}

    def test_form_urlencoded_body(self) -> None:
        """Test parsing a form-urlencoded body.

        Ensures form data is parsed into correct single and multi-value dicts.
        """
        event = {
            "headers": {"content-type": "application/x-www-form-urlencoded"},
            "body": "foo=bar&baz=123",
        }
        raw, single, multi = parse_event_body(event)
        assert raw == b"foo=bar&baz=123"
        assert single == {"foo": "bar", "baz": "123"}
        assert multi == {"foo": ["bar"], "baz": ["123"]}

    def test_base64_body(self) -> None:
        """Test parsing a base64-encoded JSON body.

        Checks that base64 decoding and JSON parsing both succeed.
        """
        json_body = '{"foo": "bar"}'
        encoded = base64.b64encode(json_body.encode("utf-8")).decode("utf-8")
        event = {
            "headers": {"content-type": "application/json"},
            "body": encoded,
            "isBase64Encoded": True,
        }
        raw, single, multi = parse_event_body(event)
        assert raw == json_body.encode("utf-8")
        assert single == {"foo": "bar"}
        assert multi == {"foo": ["bar"]}

    def test_missing_body(self) -> None:
        """Test event with missing body returns empty values.

        Ensures that missing body results in empty bytes and dicts.
        """
        event = {"headers": {"content-type": "application/json"}}
        raw, single, multi = parse_event_body(event)
        assert raw == b""
        assert single == {}
        assert multi == {}

    def test_slack_payload_nested_json(self) -> None:
        """Test Slack payload with nested JSON in form-urlencoded body.

        Verifies that a nested JSON payload is parsed into a dict.
        """
        payload = {"type": "block_actions", "user": {"id": "U123"}}
        # Slack sends as plain form-urlencoded, not base64
        event = {
            "headers": {"content-type": "application/x-www-form-urlencoded"},
            "body": f"payload={json.dumps(payload)}",
        }
        raw, single, multi = parse_event_body(event)
        assert "payload" in single
        assert isinstance(single["payload"], dict)
        assert single["payload"]["type"] == "block_actions"
        assert single["payload"]["user"]["id"] == "U123"

    def test_invalid_json_body(self) -> None:
        """Test event with invalid JSON body returns empty dicts.

        Ensures that invalid JSON does not raise and returns empty dicts.
        """
        event = {
            "headers": {"content-type": "application/json"},
            "body": "{invalid json}",
        }
        raw, single, multi = parse_event_body(event)
        assert single == {}
        assert multi == {}

    def test_unexpected_body_type(self) -> None:
        """Test event with unexpected body type (int) returns empty values.

        Ensures that non-str/bytes body types are handled gracefully.
        """
        event = {
            "headers": {"content-type": "application/json"},
            "body": 12345,
        }
        raw, single, multi = parse_event_body(event)
        assert raw == b""
        assert single == {}
        assert multi == {}
