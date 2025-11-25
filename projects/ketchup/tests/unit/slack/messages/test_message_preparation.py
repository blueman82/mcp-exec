"""
Unit tests for MessagePreparer in packages.ai.core.operations.message_preparation.

Covers:
- Initialization with mocked dependencies
- prepare_messages: all logic branches, error handling, and edge cases:
  - No instructions returned from get_prompt_for_command
  - Channel info fetch fails (exception or returns None)
  - Not a member of channel
  - Message fetch fails (exception)
  - No messages in channel
  - Normal successful path
- All external dependencies (TokenTracker, SlackChannelMessageOps, ChannelInfoOps, get_prompt_for_command) are mocked
- All tests pass mypy --strict and ruff
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.ai.core.operations.message_preparation import MessagePreparer

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_token_tracker() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_channel_msg_ops() -> MagicMock:
    mock = MagicMock()
    mock.fetch_channel_messages = AsyncMock()
    return mock


@pytest.fixture
def mock_channel_info_ops() -> MagicMock:
    mock = MagicMock()
    mock.get_channel_info_from_api = AsyncMock()
    return mock


@pytest.fixture
def preparer(
    mock_token_tracker: MagicMock,
    mock_channel_msg_ops: MagicMock,
    mock_channel_info_ops: MagicMock,
) -> MessagePreparer:
    return MessagePreparer(
        mock_token_tracker, mock_channel_msg_ops, mock_channel_info_ops
    )


@patch("packages.ai.core.operations.message_preparation.get_prompt_for_command")
@pytest.mark.asyncio
async def test_no_instructions(
    mock_get_prompt: MagicMock, preparer: MessagePreparer
) -> None:
    """Test prepare_messages raises MessagePreparationError if get_prompt_for_command returns None."""
    mock_get_prompt.return_value = None
    with pytest.raises(Exception) as excinfo:
        await preparer.prepare_messages("cmd", "U1", "C1")
    assert "No instructions generated for command" in str(excinfo.value)


@patch("packages.ai.core.operations.message_preparation.get_prompt_for_command")
@pytest.mark.asyncio
async def test_channel_info_fetch_fails(
    mock_get_prompt: MagicMock,
    preparer: MessagePreparer,
    mock_channel_info_ops: MagicMock,
) -> None:
    """Test prepare_messages raises MessagePreparationError if channel_info_ops.get_channel_info_from_api raises Exception."""
    mock_get_prompt.return_value = "instructions"
    preparer.channel_info_ops.get_channel_info_from_api = AsyncMock(
        side_effect=Exception("fail")
    )
    preparer.channel_msg_ops.fetch_channel_messages = AsyncMock(
        return_value=["msg1", "msg2"]
    )
    with pytest.raises(Exception) as excinfo:
        await preparer.prepare_messages("cmd", "U1", "C1")
    assert "Could not access channel details" in str(excinfo.value)


@patch("packages.ai.core.operations.message_preparation.get_prompt_for_command")
@pytest.mark.asyncio
async def test_channel_info_none(
    mock_get_prompt: MagicMock,
    preparer: MessagePreparer,
    mock_channel_info_ops: MagicMock,
) -> None:
    """Test prepare_messages raises MessagePreparationError if channel_info_ops.get_channel_info_from_api returns None."""
    mock_get_prompt.return_value = "instructions"
    preparer.channel_info_ops.get_channel_info_from_api = AsyncMock(return_value=None)
    preparer.channel_msg_ops.fetch_channel_messages = AsyncMock(
        return_value=["msg1", "msg2"]
    )
    with pytest.raises(Exception) as excinfo:
        await preparer.prepare_messages("cmd", "U1", "C1")
    assert "Failed to retrieve channel details" in str(excinfo.value)


@patch("packages.ai.core.operations.message_preparation.get_prompt_for_command")
@pytest.mark.asyncio
async def test_not_a_member(
    mock_get_prompt: MagicMock,
    preparer: MessagePreparer,
    mock_channel_info_ops: MagicMock,
) -> None:
    """Test prepare_messages raises MessagePreparationError if bot is not a member of the channel."""
    mock_get_prompt.return_value = "instructions"
    preparer.channel_info_ops.get_channel_info_from_api = AsyncMock(
        return_value={"name": "chan", "is_member": False, "is_archived": False}
    )
    preparer.channel_msg_ops.fetch_channel_messages = AsyncMock(
        return_value=["msg1", "msg2"]
    )
    with pytest.raises(Exception) as excinfo:
        await preparer.prepare_messages("cmd", "U1", "C1")
    assert "Ketchup is not a member of channel" in str(excinfo.value)


@patch("packages.ai.core.operations.message_preparation.get_prompt_for_command")
@pytest.mark.asyncio
async def test_message_fetch_fails(
    mock_get_prompt: MagicMock,
    preparer: MessagePreparer,
    mock_channel_info_ops: MagicMock,
    mock_channel_msg_ops: MagicMock,
) -> None:
    """Test prepare_messages raises MessagePreparationError if channel_msg_ops.fetch_channel_messages raises Exception."""
    mock_get_prompt.return_value = "instructions"
    preparer.channel_info_ops.get_channel_info_from_api = AsyncMock(
        return_value={"name": "chan", "is_member": True, "is_archived": False}
    )
    preparer.channel_msg_ops.fetch_channel_messages = AsyncMock(
        side_effect=Exception("fail")
    )
    with pytest.raises(Exception) as excinfo:
        await preparer.prepare_messages("cmd", "U1", "C1")
    # The parallel implementation doesn't include channel name in error when fetch fails
    assert "Could not fetch messages from <#C1>" in str(excinfo.value)


@patch("packages.ai.core.operations.message_preparation.get_prompt_for_command")
@pytest.mark.asyncio
async def test_no_messages(
    mock_get_prompt: MagicMock,
    preparer: MessagePreparer,
    mock_channel_info_ops: MagicMock,
    mock_channel_msg_ops: MagicMock,
) -> None:
    """Test prepare_messages handles empty message list."""
    mock_get_prompt.return_value = "instructions"
    mock_channel_info_ops.get_channel_info_from_api = AsyncMock(
        return_value={"name": "chan", "is_member": True, "is_archived": False}
    )
    mock_channel_msg_ops.fetch_channel_messages = AsyncMock(return_value=[])
    result, channel_info = await preparer.prepare_messages("cmd", "U1", "C1")
    # Check channel_info is returned correctly
    assert channel_info == {
        "target_channel": "C1",
        "channel_name": "chan",
        "originally_archived": False,
    }
    # Check that the user message content reflects no messages found
    user_message = next((m["content"] for m in result if m["role"] == "user"), None)
    # Update expected content to match the production code with the lstrip() fix
    expected_content = "(No messages found in channel)(Reference: <#C1|chan>)"
    assert user_message == expected_content


@patch("packages.ai.core.operations.message_preparation.get_prompt_for_command")
@pytest.mark.asyncio
async def test_successful_path(
    mock_get_prompt: MagicMock,
    preparer: MessagePreparer,
    mock_channel_info_ops: MagicMock,
    mock_channel_msg_ops: MagicMock,
) -> None:
    """Test prepare_messages returns formatted messages and channel info on success."""
    mock_get_prompt.return_value = "instructions"
    mock_channel_info_ops.get_channel_info_from_api = AsyncMock(
        return_value={"name": "chan", "is_member": True, "is_archived": True}
    )
    mock_channel_msg_ops.fetch_channel_messages = AsyncMock(
        return_value=["msg1", "msg2"]
    )
    result, channel_info = await preparer.prepare_messages("cmd", "U1", "C1")
    assert result[0]["role"] == "system"
    assert result[1]["role"] == "user"
    assert "msg1" in result[1]["content"]
    assert "msg2" in result[1]["content"]
    assert channel_info is not None
    assert channel_info["originally_archived"] is True


@patch("packages.ai.core.operations.message_preparation.get_prompt_for_command")
@pytest.mark.asyncio
async def test_successful_path_no_prefs(
    mock_get_prompt: MagicMock,
    preparer: MessagePreparer,
    mock_channel_info_ops: MagicMock,
    mock_channel_msg_ops: MagicMock,
) -> None:
    """Test prepare_messages success path when no user_prefs are provided."""
    mock_get_prompt.return_value = "instructions_no_prefs"
    mock_channel_info_ops.get_channel_info_from_api = AsyncMock(
        return_value={"name": "chan_no_prefs", "is_member": True, "is_archived": True}
    )
    mock_channel_msg_ops.fetch_channel_messages = AsyncMock(
        return_value=["msg1_no_prefs", "msg2_no_prefs"]
    )
    result, channel_info = await preparer.prepare_messages(
        combined_command="cmd_no_prefs",
        user_id="U1_no_prefs",
        incoming_channel="C1_no_prefs",
        normalized_user_preferences=None,  # Explicitly None
    )
    mock_get_prompt.assert_called_once_with("cmd_no_prefs", None, user_prefs=None)
    assert result[0]["content"] == "instructions_no_prefs"
    assert "msg1_no_prefs" in result[1]["content"]
    assert channel_info is not None
    assert channel_info["channel_name"] == "chan_no_prefs"


@patch("packages.ai.core.operations.message_preparation.get_prompt_for_command")
@pytest.mark.asyncio
async def test_successful_path_with_prefs(
    mock_get_prompt: MagicMock,
    preparer: MessagePreparer,
    mock_channel_info_ops: MagicMock,
    mock_channel_msg_ops: MagicMock,
) -> None:
    """Test prepare_messages success path when user_prefs are provided."""
    test_prefs = {"detail_level": "max"}
    mock_get_prompt.return_value = "instructions_with_prefs"
    mock_channel_info_ops.get_channel_info_from_api = AsyncMock(
        return_value={
            "name": "chan_with_prefs",
            "is_member": True,
            "is_archived": False,
        }
    )
    mock_channel_msg_ops.fetch_channel_messages = AsyncMock(
        return_value=["msg1_with_prefs", "msg2_with_prefs"]
    )
    result, channel_info = await preparer.prepare_messages(
        combined_command="cmd_with_prefs",
        user_id="U2_with_prefs",
        incoming_channel="C2_with_prefs",
        normalized_user_preferences=test_prefs,
    )
    # Verify get_prompt_for_command was called with user_prefs
    mock_get_prompt.assert_called_once_with(
        "cmd_with_prefs", None, user_prefs=test_prefs
    )
    assert result[0]["content"] == "instructions_with_prefs"
    assert "msg1_with_prefs" in result[1]["content"]
    assert channel_info is not None
    assert channel_info["channel_name"] == "chan_with_prefs"
    assert channel_info["originally_archived"] is False


@patch("packages.ai.core.operations.message_preparation.get_prompt_for_command")
@pytest.mark.asyncio
async def test_no_instructions_with_prefs(
    mock_get_prompt: MagicMock, preparer: MessagePreparer
) -> None:
    """Test prepare_messages raises MessagePreparationError if get_prompt_for_command returns None, with prefs."""
    mock_get_prompt.return_value = None
    test_prefs = {"detail_level": "high"}
    with pytest.raises(Exception) as excinfo:
        await preparer.prepare_messages(
            combined_command="cmd_prefs_no_instr",
            user_id="U_prefs_no_instr",
            incoming_channel="C_prefs_no_instr",
            normalized_user_preferences=test_prefs,
        )
    assert "No instructions generated for command" in str(excinfo.value)
    # Verify get_prompt_for_command was called correctly with prefs
    mock_get_prompt.assert_called_once_with(
        "cmd_prefs_no_instr", None, user_prefs=test_prefs
    )
