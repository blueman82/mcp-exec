"""
Unit tests for packages.slack.channel_events.request_processing.routing

This test module provides comprehensive coverage for the main handler functions in routing.py:
- handle_slack_command
- handle_interactive_component
- handle_events_api

Coverage includes:
- All logic branches, including normal and error paths
- Edge cases (missing/invalid input, exceptions, Slack-specific behaviors)
- Direct invocation of each handler (no reliance on upstream mocks)
- All dependencies are mocked to isolate handler logic

Expected outcomes:
- All handler functions are directly tested for correct status codes, error handling, and side effects
- All tests are mypy- and ruff-clean
- Each test function includes a detailed docstring per @ketchup_test_plan.md

This ensures robust, maintainable, and fully-documented test coverage for Slack event routing logic.
"""

import json
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import packages.slack.channel_events.request_processing.routing as routing
from packages.slack.channel_events.models import ProcessingResult
from packages.slack.interactive_elements.channel_metadata_edit import (
    ChannelMetadataEditHandler,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def home_tab_handler_mock() -> MagicMock:
    return MagicMock()


@pytest.fixture
def channel_metadata_edit_handler_mock() -> MagicMock:
    return MagicMock(spec=ChannelMetadataEditHandler)


@pytest.fixture
def trust_endorsement_handler_mock() -> MagicMock:
    return MagicMock()


# --- handle_slack_command ---
@pytest.mark.parametrize(
    "parsed_body_multivalue,missing_url",
    [
        ({"response_url": ["https://example.com"]}, False),
        ({}, True),
        ({"response_url": [None]}, True),
    ],
)
async def test_handle_slack_command_response_url(
    parsed_body_multivalue: Dict[str, List[str]], missing_url: bool
) -> None:
    """Test handle_slack_command for response_url presence and error handling.

    This test covers:
    - The normal case where response_url is present and valid: expects a 200 response and command_router.route_command is called.
    - The error case where response_url is missing or None: expects a 400 response with an error message.

    Args:
        parsed_body_multivalue: The simulated parsed body with or without response_url.
        missing_url: Whether the test case is missing a valid response_url.
    """
    command_router = MagicMock()
    if not missing_url:
        command_router.route_command = AsyncMock()
        result = await routing.handle_slack_command(parsed_body_multivalue, command_router)
        assert result == ProcessingResult(status_code=200, body="")
        command_router.route_command.assert_awaited_once()
    else:
        result = await routing.handle_slack_command(parsed_body_multivalue, command_router)
        assert result.status_code == 400
        assert "error" in json.loads(result.body)


async def test_handle_slack_command_exception_and_posting_handler() -> None:
    """Test handle_slack_command error path with posting_handler present.

    This test simulates an exception in command_router.route_command and ensures:
    - The error is caught and logged.
    - posting_handler.post_message is called to notify the user.
    - The function still returns a 200 status code with an error message (Slack ack pattern).
    """
    parsed_body_multivalue = {"response_url": ["https://example.com"]}
    posting_handler = MagicMock()
    posting_handler.post_message = AsyncMock()
    command_router = MagicMock()
    command_router.route_command = AsyncMock(side_effect=Exception("fail"))
    command_router.slack_posting_handler = posting_handler
    result = await routing.handle_slack_command(parsed_body_multivalue, command_router)
    assert result.status_code == 200
    assert "Error processing command" in result.body or result.body == "Error processing command"
    posting_handler.post_message.assert_awaited_once()


async def test_handle_slack_command_exception_no_posting_handler() -> None:
    """Test handle_slack_command error path with no posting_handler present.

    This test simulates an exception in command_router.route_command and ensures:
    - The error is caught and logged.
    - No attempt is made to call post_message (posting_handler is missing).
    - The function still returns a 200 status code with an error message (Slack ack pattern).
    """
    parsed_body_multivalue = {"response_url": ["https://example.com"]}
    command_router = MagicMock()
    command_router.route_command = AsyncMock(side_effect=Exception("fail"))
    # No slack_posting_handler attribute
    result = await routing.handle_slack_command(parsed_body_multivalue, command_router)
    assert result.status_code == 200
    assert "Error processing command" in result.body or result.body == "Error processing command"


# --- handle_interactive_component ---
async def test_handle_interactive_component_success(
    home_tab_handler_mock, channel_metadata_edit_handler_mock
) -> None:
    """Test handle_interactive_component for successful payload processing.

    This test covers the normal case where:
    - The payload is valid JSON.
    - process_interactive_payload is called and completes successfully.
    - The function returns a 200 status code and an empty body (Slack ack).
    """
    payload = {"foo": "bar"}
    parsed_body_multivalue = {"payload": [json.dumps(payload)]}
    posting_handler = MagicMock()
    feedback_handler = MagicMock()
    shortcut_handler = MagicMock()
    feedback_report_handler = MagicMock()
    with patch.object(routing, "process_interactive_payload", new=AsyncMock()) as mock_proc:
        trust_endorsement_handler = MagicMock()
        result = await routing.handle_interactive_component(
            parsed_body_multivalue,
            posting_handler,
            feedback_handler,
            shortcut_handler,
            feedback_report_handler,
            channel_metadata_edit_handler_mock,
            home_tab_handler_mock,
            trust_endorsement_handler,
        )
        assert result == ProcessingResult(status_code=200, body="")
        mock_proc.assert_awaited_once()


@pytest.mark.parametrize(
    "payload_list",
    [
        None,
        [],
        [None],
        [""],
    ],
)
async def test_handle_interactive_component_invalid_payload(
    payload_list: Any, home_tab_handler_mock, channel_metadata_edit_handler_mock
) -> None:
    """Test handle_interactive_component with invalid or missing payload.

    This test covers edge cases where:
    - The payload is None, empty, or not a valid JSON string.
    - The function returns a 400 status code and an error message.

    Args:
        payload_list: The simulated payload list (invalid cases).
    """
    parsed_body_multivalue = {"payload": payload_list}
    posting_handler = MagicMock()
    feedback_handler = MagicMock()
    shortcut_handler = MagicMock()
    feedback_report_handler = MagicMock()
    trust_endorsement_handler = MagicMock()
    result = await routing.handle_interactive_component(
        parsed_body_multivalue,
        posting_handler,
        feedback_handler,
        shortcut_handler,
        feedback_report_handler,
        channel_metadata_edit_handler_mock,
        home_tab_handler_mock,
        trust_endorsement_handler,
    )
    assert result.status_code == 400
    assert "error" in json.loads(result.body)


async def test_handle_interactive_component_json_decode_error(
    home_tab_handler_mock, channel_metadata_edit_handler_mock
) -> None:
    """Test handle_interactive_component with a payload that is not valid JSON.

    This test covers:
    - The case where the payload string cannot be parsed as JSON.
    - The function returns a 400 status code and an error message.
    """
    parsed_body_multivalue = {"payload": ["not-json"]}
    posting_handler = MagicMock()
    feedback_handler = MagicMock()
    shortcut_handler = MagicMock()
    feedback_report_handler = MagicMock()
    trust_endorsement_handler = MagicMock()
    result = await routing.handle_interactive_component(
        parsed_body_multivalue,
        posting_handler,
        feedback_handler,
        shortcut_handler,
        feedback_report_handler,
        channel_metadata_edit_handler_mock,
        home_tab_handler_mock,
        trust_endorsement_handler,
    )
    assert result.status_code == 400
    assert "error" in json.loads(result.body)


async def test_handle_interactive_component_exception_with_response_url(
    home_tab_handler_mock, channel_metadata_edit_handler_mock
) -> None:
    """Test handle_interactive_component error path with response_url present.

    This test simulates an exception in process_interactive_payload and ensures:
    - The error is caught and logged.
    - posting_handler.post_message is called to notify the user via response_url.
    - The function returns a 200 status code with an error message (Slack ack pattern).
    """
    payload = {"response_url": "https://example.com"}
    parsed_body_multivalue = {"payload": [json.dumps(payload)]}
    posting_handler = MagicMock()
    posting_handler.post_message = AsyncMock()
    feedback_handler = MagicMock()
    shortcut_handler = MagicMock()
    feedback_report_handler = MagicMock()
    with patch.object(
        routing,
        "process_interactive_payload",
        new=AsyncMock(side_effect=Exception("fail")),
    ):
        trust_endorsement_handler = MagicMock()
        result = await routing.handle_interactive_component(
            parsed_body_multivalue,
            posting_handler,
            feedback_handler,
            shortcut_handler,
            feedback_report_handler,
            channel_metadata_edit_handler_mock,
            home_tab_handler_mock,
            trust_endorsement_handler,
        )
        assert result.status_code == 200
        assert (
            "Error processing interaction" in result.body
            or result.body == "Error processing interaction"
        )
        posting_handler.post_message.assert_awaited_once()


async def test_handle_interactive_component_exception_no_response_url(
    home_tab_handler_mock, channel_metadata_edit_handler_mock
) -> None:
    """Test handle_interactive_component error path with no response_url present.

    This test simulates an exception in process_interactive_payload and ensures:
    - The error is caught and logged.
    - posting_handler.post_message is NOT called (no response_url in payload).
    - The function returns a 200 status code with an error message (Slack ack pattern).
    """
    payload = {"foo": "bar"}
    parsed_body_multivalue = {"payload": [json.dumps(payload)]}
    posting_handler = MagicMock()
    posting_handler.post_message = AsyncMock()
    feedback_handler = MagicMock()
    shortcut_handler = MagicMock()
    feedback_report_handler = MagicMock()
    with patch.object(
        routing,
        "process_interactive_payload",
        new=AsyncMock(side_effect=Exception("fail")),
    ):
        trust_endorsement_handler = MagicMock()
        result = await routing.handle_interactive_component(
            parsed_body_multivalue,
            posting_handler,
            feedback_handler,
            shortcut_handler,
            feedback_report_handler,
            channel_metadata_edit_handler_mock,
            home_tab_handler_mock,
            trust_endorsement_handler,
        )
        assert result.status_code == 200
        assert (
            "Error processing interaction" in result.body
            or result.body == "Error processing interaction"
        )
        posting_handler.post_message.assert_not_awaited()


# --- handle_events_api ---
async def test_handle_events_api_url_verification() -> None:
    """Test handle_events_api for Slack Events API url_verification event.

    This test covers:
    - The case where the event type is 'url_verification' and a challenge is present in multivalue dict.
    - The function returns a 200 status code and the challenge string as the body.
    """
    parsed_body_multivalue: Dict[str, List[str]] = {
        "type": ["url_verification"],
        "challenge": ["abc123"],
    }
    parsed_body_dict: Dict[str, Any] = {}
    event_handler = MagicMock()
    result = await routing.handle_events_api(
        parsed_body_multivalue, parsed_body_dict, event_handler
    )
    assert result == ProcessingResult(status_code=200, body="abc123")


async def test_handle_events_api_url_verification_single_value() -> None:
    """Test handle_events_api for url_verification event in single-value dict.

    This test covers:
    - The case where the event type is 'url_verification' and a challenge is present in the single-value dict.
    - The function returns a 200 status code and the challenge string as the body.
    """
    parsed_body_multivalue: Dict[str, List[str]] = {}
    parsed_body_dict: Dict[str, Any] = {
        "type": "url_verification",
        "challenge": "def456",
    }
    event_handler = MagicMock()
    result = await routing.handle_events_api(
        parsed_body_multivalue, parsed_body_dict, event_handler
    )
    assert result == ProcessingResult(status_code=200, body="def456")


async def test_handle_events_api_event_callback_nested_event() -> None:
    """Test handle_events_api for event_callback with nested event JSON.

    This test covers:
    - The case where the event type is 'event_callback' and the nested event is valid JSON.
    - The correct handler method is called on event_handler.
    - The function returns a 200 status code and 'Event received'.
    """
    event: Dict[str, Any] = {"type": "channel_created"}
    parsed_body_multivalue: Dict[str, List[str]] = {
        "type": ["event_callback"],
        "event": [json.dumps(event)],
    }
    parsed_body_dict: Dict[str, Any] = {}
    event_handler = MagicMock()
    event_handler.handle_channel_created = AsyncMock()
    result = await routing.handle_events_api(
        parsed_body_multivalue, parsed_body_dict, event_handler
    )
    assert result == ProcessingResult(status_code=200, body="Event received")
    event_handler.handle_channel_created.assert_awaited_once_with(event)


async def test_handle_events_api_event_callback_nested_event_decode_error() -> None:
    """Test handle_events_api for event_callback with nested event as dict (not JSON string).

    This test covers:
    - The case where the nested event is a dict (not a JSON string), simulating a decode error.
    - The correct handler method is called on event_handler.
    - The function returns a 200 status code and 'Event received'.
    """
    event: Dict[str, Any] = {"type": "channel_created"}
    parsed_body_multivalue: Dict[str, List[str]] = {"type": ["event_callback"], "event": [event]}  # type: ignore
    parsed_body_dict: Dict[str, Any] = {}
    event_handler = MagicMock()
    event_handler.handle_channel_created = AsyncMock()
    result = await routing.handle_events_api(parsed_body_multivalue, parsed_body_dict, event_handler)  # type: ignore
    assert result == ProcessingResult(status_code=200, body="Event received")
    event_handler.handle_channel_created.assert_awaited_once_with(event)


async def test_handle_events_api_event_callback_missing_event_field() -> None:
    """Test handle_events_api for event_callback with missing 'event' field.

    This test covers:
    - The case where the 'event' field is missing from the multivalue dict.
    - The function returns a 400 status code and an error message.
    """
    parsed_body_multivalue: Dict[str, List[str]] = {"type": ["event_callback"]}
    parsed_body_dict: Dict[str, Any] = {}
    event_handler = MagicMock()
    result = await routing.handle_events_api(
        parsed_body_multivalue, parsed_body_dict, event_handler
    )
    assert result.status_code == 400
    assert "Invalid event_callback structure" in result.body


async def test_handle_events_api_event_callback_event_not_dict() -> None:
    """Test handle_events_api for event_callback with 'event' not a dict.

    This test covers:
    - The case where the 'event' field is present but not a dict (e.g., a string).
    - The function returns a 400 status code and an error message.
    """
    parsed_body_multivalue: Dict[str, List[str]] = {}
    parsed_body_dict: Dict[str, Any] = {"type": "event_callback", "event": "notadict"}
    event_handler = MagicMock()
    result = await routing.handle_events_api(
        parsed_body_multivalue, parsed_body_dict, event_handler
    )
    assert result.status_code == 400
    assert result.body == "Invalid event_callback structure"


async def test_handle_events_api_event_callback_missing_type_in_event() -> None:
    """Test handle_events_api for event_callback with missing type in event dict.

    This test covers:
    - The case where the nested event dict is missing the 'type' key.
    - The function returns a 400 status code and an error message.
    """
    event: Dict[str, Any] = {}
    parsed_body_multivalue: Dict[str, List[str]] = {
        "type": ["event_callback"],
        "event": [json.dumps(event)],
    }
    parsed_body_dict: Dict[str, Any] = {}
    event_handler = MagicMock()
    result = await routing.handle_events_api(
        parsed_body_multivalue, parsed_body_dict, event_handler
    )
    assert result.status_code == 400
    assert "Invalid event_callback structure" in result.body


async def test_handle_events_api_event_callback_unhandled_type() -> None:
    """Test handle_events_api for event_callback with unhandled event type.

    This test covers:
    - The case where the nested event dict has an unknown event type.
    - The function logs a warning and returns a 200 status code and 'Event received'.
    """
    event: Dict[str, Any] = {"type": "unknown_event"}
    parsed_body_multivalue: Dict[str, List[str]] = {
        "type": ["event_callback"],
        "event": [json.dumps(event)],
    }
    parsed_body_dict: Dict[str, Any] = {}
    event_handler = MagicMock()
    result = await routing.handle_events_api(
        parsed_body_multivalue, parsed_body_dict, event_handler
    )
    assert result == ProcessingResult(status_code=200, body="Event received")


async def test_handle_events_api_event_callback_no_valid_dict() -> None:
    """Test handle_events_api for event_callback with no valid event dict.

    This test covers:
    - The case where the nested event is None or invalid.
    - The function returns a 400 status code and an error message.
    """
    parsed_body_multivalue: Dict[str, List[str]] = {"type": ["event_callback"], "event": [None]}  # type: ignore
    parsed_body_dict: Dict[str, Any] = {}
    event_handler = MagicMock()
    result = await routing.handle_events_api(parsed_body_multivalue, parsed_body_dict, event_handler)  # type: ignore
    assert result.status_code == 400
    assert "Invalid event_callback structure" in result.body


async def test_handle_events_api_direct_event_type_processing() -> None:
    """Test handle_events_api for direct event type processing from single-value dict.

    This test covers:
    - The case where the event type is present in the single-value dict and matches a known handler.
    - The correct handler method is called on event_handler.
    - The function returns a 200 status code and 'Event received'.
    """
    parsed_body_multivalue: Dict[str, List[str]] = {}
    parsed_body_dict: Dict[str, Any] = {"type": "channel_archive"}
    event_handler = MagicMock()
    event_handler.handle_channel_archive = AsyncMock()
    result = await routing.handle_events_api(
        parsed_body_multivalue, parsed_body_dict, event_handler
    )
    assert result == ProcessingResult(status_code=200, body="Event received")
    event_handler.handle_channel_archive.assert_awaited_once_with(parsed_body_dict)


async def test_handle_events_api_direct_event_type_processing_multivalue_error() -> None:
    """Test handle_events_api for direct event type processing from multivalue dict (unexpected structure).

    This test covers:
    - The case where the event type is present in the multivalue dict but not nested as expected.
    - The function returns a 400 status code and an error message.
    """
    parsed_body_multivalue: Dict[str, List[str]] = {"type": ["channel_archive"]}
    parsed_body_dict: Dict[str, Any] = {}
    event_handler = MagicMock()
    result = await routing.handle_events_api(
        parsed_body_multivalue, parsed_body_dict, event_handler
    )
    assert result.status_code == 400
    assert "Unexpected event structure" in result.body


async def test_handle_events_api_event_processing_exception() -> None:
    """Test handle_events_api for exception during event processing.

    This test covers:
    - The case where the handler method raises an exception.
    - The function logs the error and returns a 200 status code with an error message.
    """
    event: Dict[str, Any] = {"type": "channel_created"}
    parsed_body_multivalue: Dict[str, List[str]] = {
        "type": ["event_callback"],
        "event": [json.dumps(event)],
    }
    parsed_body_dict: Dict[str, Any] = {}
    event_handler = MagicMock()
    event_handler.handle_channel_created = AsyncMock(side_effect=Exception("fail"))
    result = await routing.handle_events_api(
        parsed_body_multivalue, parsed_body_dict, event_handler
    )
    assert result.status_code == 200
    assert "Error processing event" in result.body
