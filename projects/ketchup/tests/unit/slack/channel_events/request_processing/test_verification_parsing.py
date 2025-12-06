"""
Unit tests for packages.slack.channel_events.request_processing.verification_parsing

This module provides comprehensive tests for the verify_and_parse_body function, which handles Slack request signature verification and body parsing.

Coverage includes:
- All logic branches: base64 decoding, string/bytes body, missing/invalid body, signature verification, parsing errors
- Edge cases: invalid base64, failed signature, parse_event_body exceptions, empty bodies
- All dependencies (SlackAuth, parse_event_body) are mocked to isolate function logic

Expected outcomes:
- All branches and error cases are directly tested
- All tests are mypy- and ruff-clean
- Each test function includes a detailed docstring per @ketchup_test_plan.md
"""

# mypy: disable-error-code=var-annotated

import base64
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import packages.slack.channel_events.request_processing.verification_parsing as verification_parsing

pytestmark = pytest.mark.asyncio


@pytest.fixture
def slack_auth_mock() -> MagicMock:
    mock = MagicMock()
    mock.verify_slack_signature = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def parse_event_body_patch():
    with patch(
        "packages.slack.channel_events.request_processing.verification_parsing.parse_event_body"
    ) as mock:
        yield mock


async def test_verify_and_parse_body_base64_decoding_success(
    slack_auth_mock, parse_event_body_patch
) -> None:
    """Test base64 decoding branch with valid base64 body.

    Covers:
    - event['isBase64Encoded'] is True and body is valid base64
    - Signature verification passes
    - parse_event_body returns valid results
    - Expects correct tuple returned
    """
    raw = b"hello world"
    event = {
        "body": base64.b64encode(raw).decode(),
        "isBase64Encoded": True,
        "headers": {},
    }
    parse_event_body_patch.return_value = (raw, {"foo": "bar"}, {"foo": ["bar"]})
    result = await verification_parsing.verify_and_parse_body(event, slack_auth_mock)
    assert result == (raw, {"foo": "bar"}, {"foo": ["bar"]})
    slack_auth_mock.verify_slack_signature.assert_awaited_once()
    parse_event_body_patch.assert_called_once()


async def test_verify_and_parse_body_base64_decoding_failure(slack_auth_mock) -> None:
    """Test base64 decoding branch with invalid base64 body.

    Covers:
    - event['isBase64Encoded'] is True and body is invalid base64
    - Expects function to return (None, None, None)
    """
    event = {
        "body": "notbase64!",
        "isBase64Encoded": True,
        "headers": {},
    }
    result = await verification_parsing.verify_and_parse_body(event, slack_auth_mock)
    assert result == (None, None, None)
    slack_auth_mock.verify_slack_signature.assert_not_awaited()


async def test_verify_and_parse_body_string_body(slack_auth_mock, parse_event_body_patch) -> None:
    """Test string body branch.

    Covers:
    - event['body'] is a string and not base64 encoded
    - Signature verification passes
    - parse_event_body returns valid results
    - Expects correct tuple returned
    """
    body = "plain text"
    event = {"body": body, "headers": {}}
    parse_event_body_patch.return_value = (body.encode(), {"a": 1}, {"a": ["1"]})
    result = await verification_parsing.verify_and_parse_body(event, slack_auth_mock)
    assert result == (body.encode(), {"a": 1}, {"a": ["1"]})
    slack_auth_mock.verify_slack_signature.assert_awaited_once()
    parse_event_body_patch.assert_called_once()


async def test_verify_and_parse_body_bytes_body(slack_auth_mock, parse_event_body_patch) -> None:
    """Test bytes body branch.

    Covers:
    - event['body'] is already bytes
    - Signature verification passes
    - parse_event_body returns valid results
    - Expects correct tuple returned
    """
    body = b"bytes body"
    event = {"body": body, "headers": {}}
    parse_event_body_patch.return_value = (body, {"b": 2}, {"b": ["2"]})
    result = await verification_parsing.verify_and_parse_body(event, slack_auth_mock)
    assert result == (body, {"b": 2}, {"b": ["2"]})
    slack_auth_mock.verify_slack_signature.assert_awaited_once()
    parse_event_body_patch.assert_called_once()


async def test_verify_and_parse_body_unexpected_body_type(slack_auth_mock) -> None:
    """Test unexpected body type branch.

    Covers:
    - event['body'] is an unsupported type (e.g., int)
    - Expects function to return (None, None, None)
    """
    event = {"body": 123, "headers": {}}
    result = await verification_parsing.verify_and_parse_body(event, slack_auth_mock)
    assert result == (None, None, None)
    slack_auth_mock.verify_slack_signature.assert_not_awaited()


async def test_verify_and_parse_body_missing_body(slack_auth_mock, parse_event_body_patch) -> None:
    """Test missing or empty body branch.

    Covers:
    - event['body'] is missing or empty
    - raw_body_bytes is set to b""
    - Signature verification passes
    - parse_event_body returns valid results
    - Expects correct tuple returned
    """
    event = {"headers": {}}
    parse_event_body_patch.return_value = (b"", {"c": 3}, {"c": ["3"]})
    result = await verification_parsing.verify_and_parse_body(event, slack_auth_mock)
    assert result == (b"", {"c": 3}, {"c": ["3"]})
    slack_auth_mock.verify_slack_signature.assert_awaited_once()
    parse_event_body_patch.assert_called_once()


async def test_verify_and_parse_body_signature_verification_fails(
    slack_auth_mock,
) -> None:
    """Test signature verification failure branch.

    Covers:
    - slack_auth.verify_slack_signature returns False
    - Expects function to return (None, None, None)
    """
    slack_auth_mock.verify_slack_signature = AsyncMock(return_value=False)
    event = {"body": "irrelevant", "headers": {}}
    result = await verification_parsing.verify_and_parse_body(event, slack_auth_mock)
    assert result == (None, None, None)


TEST_INPUT_PARSE_EXCEPTION: Dict[str, Any] = {"body": "irrelevant", "headers": {}}


async def test_verify_and_parse_body_parse_event_body_exception(
    slack_auth_mock,
) -> None:
    """Test parse_event_body exception branch.

    Covers:
    - parse_event_body raises an exception
    - Expects the exception to propagate out of verify_and_parse_body
    """
    with patch(
        "packages.slack.channel_events.request_processing.verification_parsing.parse_event_body",
        side_effect=Exception("fail parse"),
    ):
        # Assert that the specific exception raised by the mock propagates
        with pytest.raises(Exception, match="fail parse"):
            await verification_parsing.verify_and_parse_body(
                TEST_INPUT_PARSE_EXCEPTION, slack_auth_mock
            )
        # Signature verification IS awaited before parse_event_body is called.
        # If parse_event_body fails, verify_slack_signature would have already been called.
        slack_auth_mock.verify_slack_signature.assert_awaited_once()


# Commenting out tests for parse_verification_request as the function seems to be missing
# from the provided codebase context.

# @pytest.mark.parametrize(
#     "body",
#     [
#         b"bytes body", # Test with bytes
#         "string body",  # Test with string
#         "",             # Test with empty string
#         None,           # Test with None
#         123,            # Test with integer
#         {},             # Test with dict
#     ],
# )
# async def test_parse_verification_request_invalid_payload(body: Any) -> None:
#     """Test parse_verification_request with various invalid or empty payloads.

#     Covers:
#     - Payloads that are not query strings or are malformed
#     - Expects (None, None, None) for all invalid cases
#     """
#     # Assuming parse_verification_request is synchronous or we mock an async wrapper if needed.
#     # For this example, let's assume it's a simple synchronous utility.
#     # If it's part of an async flow, the test setup might differ.
#     result = verification_parsing.parse_verification_request(body) # This function is not found
#     assert result == (None, None, None)
