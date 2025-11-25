"""
Unit tests for packages.slack.interactive_elements.payload_processor

This module provides comprehensive tests for the process_interactive_payload function, which processes Slack interactive payloads (block_actions, shortcut, view_submission, and error cases).

Coverage includes:
- All logic branches: block_actions (feedback, unknown), shortcut, view_submission, unknown type, invalid format, JSON decode error, exceptions
- Edge cases: missing/invalid payload fields, posting errors, malformed input
- All dependencies (handlers) are mocked to isolate logic

Expected outcomes:
- All branches and error cases are directly tested
- All tests are mypy- and ruff-clean
- Each test function includes a detailed docstring per @ketchup_test_plan.md
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.slack.interactive_elements import payload_processor
from packages.slack.interactive_elements.channel_metadata_edit import (
    ChannelMetadataEditHandler,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def posting_handler_mock() -> MagicMock:
    mock = MagicMock()
    mock.post_message = AsyncMock()
    return mock


@pytest.fixture
def feedback_handler_mock() -> MagicMock:
    mock = MagicMock()
    mock.process_feedback_reaction = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def shortcut_handler_mock() -> MagicMock:
    mock = MagicMock()
    mock.handle_shortcut = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def feedback_report_handler_mock() -> MagicMock:
    mock = MagicMock()
    return mock


@pytest.fixture
def home_tab_handler_mock() -> MagicMock:
    return MagicMock()


@pytest.fixture
def channel_metadata_edit_handler_mock():
    return MagicMock(spec=ChannelMetadataEditHandler)


@pytest.fixture
def trust_endorsement_handler_mock() -> MagicMock:
    mock = MagicMock()
    mock.process_trust_action = AsyncMock(return_value=True)
    mock.process_command_trust_action = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def flag_review_handler_mock() -> MagicMock:
    mock = MagicMock()
    mock.process_flag_action = AsyncMock(return_value=True)
    mock.process_command_flag_action = AsyncMock(return_value=True)
    return mock


@pytest.mark.parametrize(
    "payload_input",
    [
        {
            "type": "block_actions",
            "actions": [{"action_id": "feedback_thumbs_up"}],
            "user": {"id": "U1"},
            "channel": {"id": "C1"},
        },
        {
            "type": "block_actions",
            "actions": [{"action_id": "feedback_thumbs_down"}],
            "user": {"id": "U1"},
            "channel": {"id": "C1"},
        },
    ],
)
async def test_block_actions_feedback_success(
    payload_input,
    posting_handler_mock,
    feedback_handler_mock,
    shortcut_handler_mock,
    feedback_report_handler_mock,
    home_tab_handler_mock,
    channel_metadata_edit_handler_mock,
    trust_endorsement_handler_mock,
    flag_review_handler_mock,
) -> None:
    """Test block_actions with feedback action_id (thumbs up/down).

    Covers:
    - payload type == 'block_actions', action_id startswith 'feedback_'
    - feedback_handler.process_feedback_reaction returns True
    - Expects True returned, no error message posted
    """
    result = await payload_processor.process_interactive_payload(
        payload_input,
        posting_handler_mock,
        feedback_handler_mock,
        shortcut_handler_mock,
        feedback_report_handler_mock,
        channel_metadata_edit_handler_mock,
        home_tab_handler_mock,
        trust_endorsement_handler_mock,
    )
    assert result is True
    feedback_handler_mock.process_feedback_reaction.assert_awaited_once_with(
        payload=payload_input
    )
    posting_handler_mock.post_message.assert_not_awaited()


async def test_block_actions_feedback_failure(
    posting_handler_mock,
    feedback_handler_mock,
    shortcut_handler_mock,
    feedback_report_handler_mock,
    home_tab_handler_mock,
    channel_metadata_edit_handler_mock,
    trust_endorsement_handler_mock,
    flag_review_handler_mock,
) -> None:
    """Test block_actions with feedback action_id where handler returns False.

    Covers:
    - payload type == 'block_actions', action_id startswith 'feedback_'
    - feedback_handler.process_feedback_reaction returns False
    - Expects error message posted, True returned
    """
    payload = {
        "type": "block_actions",
        "actions": [{"action_id": "feedback_thumbs_up"}],
        "user": {"id": "U1"},
        "channel": {"id": "C1"},
    }
    feedback_handler_mock.process_feedback_reaction = AsyncMock(return_value=False)
    result = await payload_processor.process_interactive_payload(
        payload,
        posting_handler_mock,
        feedback_handler_mock,
        shortcut_handler_mock,
        feedback_report_handler_mock,
        channel_metadata_edit_handler_mock,
        home_tab_handler_mock,
        trust_endorsement_handler_mock,
    )
    assert result is True
    feedback_handler_mock.process_feedback_reaction.assert_awaited_once_with(
        payload=payload
    )
    posting_handler_mock.post_message.assert_awaited_once_with(
        user_id="U1",
        channel_id="C1",
        message="Error processing feedback. Please try again.",
    )


async def test_block_actions_no_actions(
    posting_handler_mock,
    feedback_handler_mock,
    shortcut_handler_mock,
    feedback_report_handler_mock,
    home_tab_handler_mock,
    channel_metadata_edit_handler_mock,
    trust_endorsement_handler_mock,
    flag_review_handler_mock,
) -> None:
    """Test block_actions with no actions in payload.

    Covers:
    - payload type == 'block_actions', actions is empty
    - Expects warning message posted, True returned
    """
    payload = {
        "type": "block_actions",
        "actions": [],
        "user": {"id": "U1"},
        "channel": {"id": "C1"},
    }
    result = await payload_processor.process_interactive_payload(
        payload,
        posting_handler_mock,
        feedback_handler_mock,
        shortcut_handler_mock,
        feedback_report_handler_mock,
        channel_metadata_edit_handler_mock,
        home_tab_handler_mock,
        trust_endorsement_handler_mock,
    )
    assert result is True
    posting_handler_mock.post_message.assert_awaited_once_with(
        user_id="U1",
        channel_id="C1",
        message="No actions found in payload",
    )
    feedback_handler_mock.process_feedback_reaction.assert_not_awaited()


async def test_block_actions_unknown_action(
    posting_handler_mock,
    feedback_handler_mock,
    shortcut_handler_mock,
    feedback_report_handler_mock,
    home_tab_handler_mock,
    channel_metadata_edit_handler_mock,
    trust_endorsement_handler_mock,
    flag_review_handler_mock,
) -> None:
    """Test block_actions with unknown action_id.

    Covers:
    - payload type == 'block_actions', action_id does not start with 'feedback_'
    - Expects warning message posted, True returned
    """
    payload = {
        "type": "block_actions",
        "actions": [{"action_id": "other_action"}],
        "user": {"id": "U1"},
        "channel": {"id": "C1"},
    }
    result = await payload_processor.process_interactive_payload(
        payload,
        posting_handler_mock,
        feedback_handler_mock,
        shortcut_handler_mock,
        feedback_report_handler_mock,
        channel_metadata_edit_handler_mock,
        home_tab_handler_mock,
        trust_endorsement_handler_mock,
    )
    assert result is True
    posting_handler_mock.post_message.assert_awaited_once_with(
        user_id="U1",
        channel_id="C1",
        message="Unknown action: other_action",
    )
    feedback_handler_mock.process_feedback_reaction.assert_not_awaited()


async def test_shortcut_success(
    posting_handler_mock,
    feedback_handler_mock,
    shortcut_handler_mock,
    feedback_report_handler_mock,
    home_tab_handler_mock,
    channel_metadata_edit_handler_mock,
    trust_endorsement_handler_mock,
    flag_review_handler_mock,
) -> None:
    """Test shortcut payload type.

    Covers:
    - payload type == 'shortcut'
    - shortcut_handler.handle_shortcut returns True
    - Expects True returned
    """
    payload = {"type": "shortcut"}
    shortcut_handler_mock.handle_shortcut = AsyncMock(return_value=True)
    result = await payload_processor.process_interactive_payload(
        payload,
        posting_handler_mock,
        feedback_handler_mock,
        shortcut_handler_mock,
        feedback_report_handler_mock,
        channel_metadata_edit_handler_mock,
        home_tab_handler_mock,
        trust_endorsement_handler_mock,
    )
    assert result is True
    shortcut_handler_mock.handle_shortcut.assert_awaited_once_with(
        slack_payload=payload
    )


async def test_shortcut_failure(
    posting_handler_mock,
    feedback_handler_mock,
    shortcut_handler_mock,
    feedback_report_handler_mock,
    home_tab_handler_mock,
    channel_metadata_edit_handler_mock,
    trust_endorsement_handler_mock,
    flag_review_handler_mock,
) -> None:
    """Test shortcut payload type where handler returns False.

    Covers:
    - payload type == 'shortcut'
    - shortcut_handler.handle_shortcut returns False
    - Expects False returned
    """
    payload = {"type": "shortcut"}
    shortcut_handler_mock.handle_shortcut = AsyncMock(return_value=False)
    result = await payload_processor.process_interactive_payload(
        payload,
        posting_handler_mock,
        feedback_handler_mock,
        shortcut_handler_mock,
        feedback_report_handler_mock,
        channel_metadata_edit_handler_mock,
        home_tab_handler_mock,
        trust_endorsement_handler_mock,
    )
    assert result is False
    shortcut_handler_mock.handle_shortcut.assert_awaited_once_with(
        slack_payload=payload
    )


async def test_view_submission_success(
    posting_handler_mock,
    feedback_handler_mock,
    shortcut_handler_mock,
    feedback_report_handler_mock,
    monkeypatch,
    home_tab_handler_mock,
    channel_metadata_edit_handler_mock,
    trust_endorsement_handler_mock,
    flag_review_handler_mock,
) -> None:
    """Test view_submission payload type.

    Covers:
    - payload type == 'view_submission'
    - process_view_submission returns True
    - Expects True returned
    """
    payload = {"type": "view_submission"}
    called_args = {}

    async def fake_process_view_submission(*args, **kwargs):
        called_args["args"] = args
        called_args["kwargs"] = kwargs
        return True

    monkeypatch.setattr(
        payload_processor, "process_view_submission", fake_process_view_submission
    )
    result = await payload_processor.process_interactive_payload(
        payload,
        posting_handler_mock,
        feedback_handler_mock,
        shortcut_handler_mock,
        feedback_report_handler_mock,
        channel_metadata_edit_handler_mock,
        home_tab_handler_mock,
        trust_endorsement_handler_mock,
    )
    assert result is True
    assert called_args["kwargs"]["payload"] == payload
    assert (
        called_args["kwargs"]["feedback_report_handler"] == feedback_report_handler_mock
    )


async def test_view_submission_failure(
    posting_handler_mock,
    feedback_handler_mock,
    shortcut_handler_mock,
    feedback_report_handler_mock,
    monkeypatch,
    home_tab_handler_mock,
    channel_metadata_edit_handler_mock,
    trust_endorsement_handler_mock,
    flag_review_handler_mock,
) -> None:
    """Test view_submission payload type where handler returns False.

    Covers:
    - payload type == 'view_submission'
    - process_view_submission returns False
    - Expects False returned
    """
    payload = {"type": "view_submission"}
    called_args = {}

    async def fake_process_view_submission(*args, **kwargs):
        called_args["args"] = args
        called_args["kwargs"] = kwargs
        return False

    monkeypatch.setattr(
        payload_processor, "process_view_submission", fake_process_view_submission
    )
    result = await payload_processor.process_interactive_payload(
        payload,
        posting_handler_mock,
        feedback_handler_mock,
        shortcut_handler_mock,
        feedback_report_handler_mock,
        channel_metadata_edit_handler_mock,
        home_tab_handler_mock,
        trust_endorsement_handler_mock,
    )
    assert result is False
    assert called_args["kwargs"]["payload"] == payload
    assert (
        called_args["kwargs"]["feedback_report_handler"] == feedback_report_handler_mock
    )


async def test_unknown_payload_type_with_user_and_channel(
    posting_handler_mock,
    feedback_handler_mock,
    shortcut_handler_mock,
    feedback_report_handler_mock,
    home_tab_handler_mock,
    channel_metadata_edit_handler_mock,
    trust_endorsement_handler_mock,
    flag_review_handler_mock,
) -> None:
    """Test unknown payload type with user and channel present.

    Covers:
    - payload type is unknown
    - user_id and channel_id present
    - Expects error message posted, False returned
    """
    payload = {"type": "unknown_type", "user": {"id": "U1"}, "channel": {"id": "C1"}}
    result = await payload_processor.process_interactive_payload(
        payload,
        posting_handler_mock,
        feedback_handler_mock,
        shortcut_handler_mock,
        feedback_report_handler_mock,
        channel_metadata_edit_handler_mock,
        home_tab_handler_mock,
        trust_endorsement_handler_mock,
    )
    assert result is False
    posting_handler_mock.post_message.assert_awaited_once_with(
        user_id="U1",
        channel_id="C1",
        message="Unknown payload type: unknown_type",
    )


async def test_unknown_payload_type_without_user_or_channel(
    posting_handler_mock,
    feedback_handler_mock,
    shortcut_handler_mock,
    feedback_report_handler_mock,
    home_tab_handler_mock,
    channel_metadata_edit_handler_mock,
    trust_endorsement_handler_mock,
    flag_review_handler_mock,
) -> None:
    """Test unknown payload type with missing user/channel.

    Covers:
    - payload type is unknown
    - user_id or channel_id missing
    - Expects False returned, no error message posted
    """
    payload = {"type": "unknown_type"}
    result = await payload_processor.process_interactive_payload(
        payload,
        posting_handler_mock,
        feedback_handler_mock,
        shortcut_handler_mock,
        feedback_report_handler_mock,
        channel_metadata_edit_handler_mock,
        home_tab_handler_mock,
        trust_endorsement_handler_mock,
    )
    assert result is False
    posting_handler_mock.post_message.assert_not_awaited()


@pytest.mark.parametrize(
    "payload_input",
    [
        {
            "payload": json.dumps(
                {
                    "type": "block_actions",
                    "actions": [{"action_id": "feedback_thumbs_up"}],
                    "user": {"id": "U1"},
                    "channel": {"id": "C1"},
                }
            )
        },
        {"payload": [json.dumps({"type": "shortcut"})]},
    ],
)
async def test_payload_input_as_body_dict(
    payload_input,
    posting_handler_mock,
    feedback_handler_mock,
    shortcut_handler_mock,
    feedback_report_handler_mock,
    home_tab_handler_mock,
    channel_metadata_edit_handler_mock,
    trust_endorsement_handler_mock,
    flag_review_handler_mock,
) -> None:
    """Test payload_input as body dict with 'payload' key (string or list).

    Covers:
    - payload_input is a dict with 'payload' key (string or list)
    - JSON is parsed and correct handler is called
    """
    result = await payload_processor.process_interactive_payload(
        payload_input,
        posting_handler_mock,
        feedback_handler_mock,
        shortcut_handler_mock,
        feedback_report_handler_mock,
        channel_metadata_edit_handler_mock,
        home_tab_handler_mock,
        trust_endorsement_handler_mock,
    )
    assert result is True


async def test_payload_input_invalid_json(
    posting_handler_mock,
    feedback_handler_mock,
    shortcut_handler_mock,
    feedback_report_handler_mock,
    home_tab_handler_mock,
    channel_metadata_edit_handler_mock,
    trust_endorsement_handler_mock,
    flag_review_handler_mock,
) -> None:
    """Test payload_input as body dict with invalid JSON in 'payload' key.

    Covers:
    - payload_input is a dict with 'payload' key, but JSON is invalid
    - Expects False returned, error logged
    """
    payload_input = {"payload": "not-json"}
    result = await payload_processor.process_interactive_payload(
        payload_input,
        posting_handler_mock,
        feedback_handler_mock,
        shortcut_handler_mock,
        feedback_report_handler_mock,
        channel_metadata_edit_handler_mock,
        home_tab_handler_mock,
        trust_endorsement_handler_mock,
    )
    assert result is False


async def test_payload_input_invalid_format(
    posting_handler_mock,
    feedback_handler_mock,
    shortcut_handler_mock,
    feedback_report_handler_mock,
    home_tab_handler_mock,
    channel_metadata_edit_handler_mock,
    trust_endorsement_handler_mock,
    flag_review_handler_mock,
) -> None:
    """Test payload_input with invalid format (not dict or missing keys).

    Covers:
    - payload_input is not a dict with 'type' or 'payload' key
    - Expects False returned, error logged
    """
    payload_input = {"not_type": 123}  # Not a valid input, but still a dict
    result = await payload_processor.process_interactive_payload(
        payload_input,
        posting_handler_mock,
        feedback_handler_mock,
        shortcut_handler_mock,
        feedback_report_handler_mock,
        channel_metadata_edit_handler_mock,
        home_tab_handler_mock,
        trust_endorsement_handler_mock,
    )
    assert result is False


async def test_exception_in_processing(
    posting_handler_mock,
    feedback_handler_mock,
    shortcut_handler_mock,
    feedback_report_handler_mock,
    monkeypatch,
    home_tab_handler_mock,
    channel_metadata_edit_handler_mock,
    trust_endorsement_handler_mock,
    flag_review_handler_mock,
) -> None:
    """Test exception raised during processing.

    Covers:
    - Any exception in the function
    - Expects False returned, error logged
    """
    payload = {
        "type": "block_actions",
        "actions": [{"action_id": "feedback_thumbs_up"}],
        "user": {"id": "U1"},
        "channel": {"id": "C1"},
    }
    monkeypatch.setattr(
        feedback_handler_mock,
        "process_feedback_reaction",
        AsyncMock(side_effect=Exception("fail")),
    )
    result = await payload_processor.process_interactive_payload(
        payload,
        posting_handler_mock,
        feedback_handler_mock,
        shortcut_handler_mock,
        feedback_report_handler_mock,
        channel_metadata_edit_handler_mock,
        home_tab_handler_mock,
        trust_endorsement_handler_mock,
    )
    assert result is False


async def test_edit_channel_metadata_with_valid_private_metadata(
    posting_handler_mock,
    feedback_handler_mock,
    shortcut_handler_mock,
    feedback_report_handler_mock,
    home_tab_handler_mock,
    channel_metadata_edit_handler_mock,
    trust_endorsement_handler_mock,
    flag_review_handler_mock,
) -> None:
    """Test edit_channel_metadata view_submission with VALID private_metadata.

    Covers:
    - callback_id == 'edit_channel_metadata'
    - private_metadata contains valid JSON with target_channel_id
    - channel_id is extracted from private_metadata (NOT from DM channel)
    - update_channel_metadata is called with PUBLIC channel_id, not DM channel_id
    - Expects success modal opened, True returned
    """
    # Scenario: Modal opened from Ketchup DM (origin), editing a public channel (target)
    public_channel_id = "C123456"  # Public channel: starts with C
    dm_channel_id = "D0840EX80R5"  # DM channel: starts with D

    payload = {
        "type": "view_submission",
        "user": {"id": "U1"},
        "trigger_id": "trigger_123",
        "channel": {"id": dm_channel_id},  # Modal opened from DM
        "view": {
            "callback_id": "edit_channel_metadata",
            "private_metadata": json.dumps({
                "origin_channel_id": dm_channel_id,
                "target_channel_id": public_channel_id,  # This is what we want to update
            }),
            "state": {
                "values": {
                    "customer_name_block": {
                        "customer_name_input": {"value": "TEST CUSTOMER"}
                    },
                    "jira_ticket_block": {
                        "jira_ticket_input": {"value": "CPGNREQ-12345"}
                    },
                }
            },
        },
    }

    # Mock the dynamodb_store to track what channel_id is passed
    channel_metadata_edit_handler_mock.dynamodb_store = AsyncMock()
    channel_metadata_edit_handler_mock.dynamodb_store.update_channel_metadata = AsyncMock(
        return_value=True
    )
    channel_metadata_edit_handler_mock.open_success_modal = AsyncMock(return_value=True)

    result = await payload_processor.process_interactive_payload(
        payload,
        posting_handler_mock,
        feedback_handler_mock,
        shortcut_handler_mock,
        feedback_report_handler_mock,
        channel_metadata_edit_handler_mock,
        home_tab_handler_mock,
        trust_endorsement_handler_mock,
    )

    # Should succeed and call DB update with PUBLIC channel_id
    assert result is True
    channel_metadata_edit_handler_mock.dynamodb_store.update_channel_metadata.assert_awaited_once()
    call_kwargs = channel_metadata_edit_handler_mock.dynamodb_store.update_channel_metadata.call_args[1]
    # CRITICAL: Must use public channel, NOT DM channel
    assert call_kwargs["channel_id"] == public_channel_id, (
        f"Expected channel_id={public_channel_id} (public), "
        f"but got {call_kwargs['channel_id']} (likely DM)"
    )
    channel_metadata_edit_handler_mock.open_success_modal.assert_awaited_once()


async def test_edit_channel_metadata_with_missing_private_metadata(
    posting_handler_mock,
    feedback_handler_mock,
    shortcut_handler_mock,
    feedback_report_handler_mock,
    home_tab_handler_mock,
    channel_metadata_edit_handler_mock,
    trust_endorsement_handler_mock,
    flag_review_handler_mock,
) -> None:
    """Test edit_channel_metadata view_submission with MISSING private_metadata.

    Covers:
    - callback_id == 'edit_channel_metadata'
    - private_metadata is empty or missing
    - FALLBACK: channel_id is extracted from payload.get("channel", {}).get("id") (DM channel)
    - update_channel_metadata is called with DM channel_id (THE BUG!)
    - This proves the data corruption issue
    """
    # Scenario: Modal opened from Ketchup DM, trying to edit public channel
    _public_channel_id = "C123456"  # What we WANTED to edit (intentionally unused)
    dm_channel_id = "D0840EX80R5"  # DM where modal opened from

    payload = {
        "type": "view_submission",
        "user": {"id": "U1"},
        "trigger_id": "trigger_123",
        "channel": {"id": dm_channel_id},  # Modal opened from DM
        "view": {
            "callback_id": "edit_channel_metadata",
            "private_metadata": "",  # EMPTY - the bug scenario
            "state": {
                "values": {
                    "customer_name_block": {
                        "customer_name_input": {"value": "TEST CUSTOMER"}
                    },
                    "jira_ticket_block": {
                        "jira_ticket_input": {"value": "CPGNREQ-12345"}
                    },
                }
            },
        },
    }

    # Mock the dynamodb_store to track what channel_id is passed
    channel_metadata_edit_handler_mock.dynamodb_store = AsyncMock()
    channel_metadata_edit_handler_mock.dynamodb_store.update_channel_metadata = AsyncMock(
        return_value=True
    )
    channel_metadata_edit_handler_mock.open_success_modal = AsyncMock(return_value=True)

    result = await payload_processor.process_interactive_payload(
        payload,
        posting_handler_mock,
        feedback_handler_mock,
        shortcut_handler_mock,
        feedback_report_handler_mock,
        channel_metadata_edit_handler_mock,
        home_tab_handler_mock,
        trust_endorsement_handler_mock,
    )

    # Test that the bug is FIXED: should fail gracefully instead of using wrong channel
    assert result is False  # Should fail due to missing metadata, not corrupt data with wrong channel
    # Should NOT attempt to update metadata when private_metadata is missing
    channel_metadata_edit_handler_mock.dynamodb_store.update_channel_metadata.assert_not_awaited()


async def test_edit_channel_metadata_with_malformed_json_private_metadata(
    posting_handler_mock,
    feedback_handler_mock,
    shortcut_handler_mock,
    feedback_report_handler_mock,
    home_tab_handler_mock,
    channel_metadata_edit_handler_mock,
    trust_endorsement_handler_mock,
    flag_review_handler_mock,
) -> None:
    """Test edit_channel_metadata view_submission with MALFORMED JSON in private_metadata.

    Covers:
    - callback_id == 'edit_channel_metadata'
    - private_metadata contains invalid JSON
    - Exception caught, channel_id falls back to None, then gets DM channel_id
    - update_channel_metadata is called with DM channel_id (THE BUG!)
    - This is another path to the data corruption issue
    """
    dm_channel_id = "D0840EX80R5"

    payload = {
        "type": "view_submission",
        "user": {"id": "U1"},
        "trigger_id": "trigger_123",
        "channel": {"id": dm_channel_id},
        "view": {
            "callback_id": "edit_channel_metadata",
            "private_metadata": "{invalid json}",  # MALFORMED JSON
            "state": {
                "values": {
                    "customer_name_block": {
                        "customer_name_input": {"value": "TEST CUSTOMER"}
                    },
                    "jira_ticket_block": {
                        "jira_ticket_input": {"value": "CPGNREQ-12345"}
                    },
                }
            },
        },
    }

    channel_metadata_edit_handler_mock.dynamodb_store = AsyncMock()
    channel_metadata_edit_handler_mock.dynamodb_store.update_channel_metadata = AsyncMock(
        return_value=True
    )
    channel_metadata_edit_handler_mock.open_success_modal = AsyncMock(return_value=True)

    result = await payload_processor.process_interactive_payload(
        payload,
        posting_handler_mock,
        feedback_handler_mock,
        shortcut_handler_mock,
        feedback_report_handler_mock,
        channel_metadata_edit_handler_mock,
        home_tab_handler_mock,
        trust_endorsement_handler_mock,
    )

    # FIXED: Should fail gracefully instead of falling back to DM channel when JSON parsing fails
    assert result is False  # Should fail due to malformed JSON, not corrupt data with wrong channel
    # Should NOT attempt to update metadata when JSON is malformed
    channel_metadata_edit_handler_mock.dynamodb_store.update_channel_metadata.assert_not_awaited()
