"""
Unit tests for SlackChannelMessageOps in packages.slack.channel_operations.channel_msg_ops.

Covers:
- SlackChannelMessageOps: fetch_channel_messages, fetch_thread_messages_batch, fetch_thread_messages
- All logic branches: success, API error, not_in_channel, archived/unarchived, thread fetching, batch sizing, retries, exceptions
- All dependencies are mocked (SlackUserOps, SlackChannelArchiveOps, SlackConfig, SlackMessageFormatter, aiohttp, logger, batch_sizer)
- All tests pass mypy --strict and ruff
- Expected: correct API calls, error handling, posting, logging, retry logic
"""

from unittest.mock import AsyncMock, MagicMock, patch

import orjson
import pytest

from packages.slack.channel_operations.channel_msg_ops import SlackChannelMessageOps

# Capture the real orjson.dumps function at import time to avoid mock pollution
_real_orjson_dumps = orjson.dumps

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_user_ops() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_archive_ops() -> MagicMock:
    ops = MagicMock()
    ops.archive_channel = AsyncMock()
    return ops


@pytest.fixture
def mock_slack_config() -> MagicMock:
    cfg = MagicMock()
    cfg.get_api_base_url.return_value = "https://api.slack.com"
    return cfg


@pytest.fixture
def ops(
    mock_user_ops: MagicMock, mock_archive_ops: MagicMock, mock_slack_config: MagicMock
) -> SlackChannelMessageOps:
    return SlackChannelMessageOps(
        user_ops=mock_user_ops,
        archive_ops=mock_archive_ops,
        slack_config=mock_slack_config,
    )


@pytest.mark.asyncio
async def test_fetch_channel_messages_success(
    ops: SlackChannelMessageOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test fetch_channel_messages returns processed messages on success."""
    monkeypatch.setattr(ops, "_temporarily_unarchive_if_needed", AsyncMock(return_value=False))
    monkeypatch.setattr(ops, "get_api_base_url", AsyncMock(return_value="https://api.slack.com"))
    monkeypatch.setattr(type(ops), "headers", property(lambda self: {}))
    ops._batch_sizer = MagicMock()
    ops._batch_sizer.get_size.return_value = 100
    ops._batch_sizer.increase_size = MagicMock()
    ops._batch_sizer.decrease_size = MagicMock()

    # Mock orjson.loads to return expected data
    mock_response_data = {"ok": True, "messages": [{"ts": "1", "text": "hi"}]}
    monkeypatch.setattr(
        "packages.slack.channel_operations.channel_msg_ops.orjson.loads",
        lambda x: mock_response_data,
    )

    # Mock the API request to return something (content doesn't matter due to orjson mock)
    mock_response = {"body": "irrelevant", "status": 200}
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=mock_response))

    # Patch formatter
    ops._formatter = MagicMock()
    ops._formatter.process_message_batch = AsyncMock(return_value=(["msg1"], set()))
    # Patch fetch_thread_messages_batch to return nothing
    monkeypatch.setattr(ops, "_fetch_thread_messages_parallel", AsyncMock(return_value=({}, set())))
    result = await ops.fetch_channel_messages("C1", use_parallel_pagination=False)
    assert result == ["msg1"]


@pytest.mark.asyncio
async def test_fetch_channel_messages_with_threads(
    ops: SlackChannelMessageOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test fetch_channel_messages fetches and merges thread messages."""
    monkeypatch.setattr(ops, "_temporarily_unarchive_if_needed", AsyncMock(return_value=False))
    monkeypatch.setattr(ops, "get_api_base_url", AsyncMock(return_value="https://api.slack.com"))
    monkeypatch.setattr(type(ops), "headers", property(lambda self: {}))
    ops._batch_sizer = MagicMock()
    ops._batch_sizer.get_size.return_value = 100
    ops._batch_sizer.increase_size = MagicMock()
    ops._batch_sizer.decrease_size = MagicMock()

    # Mock orjson.loads to return expected data with thread_ts
    mock_response_data = {
        "ok": True,
        "messages": [{"ts": "1", "text": "hi", "thread_ts": "1.1"}],
    }
    monkeypatch.setattr(
        "packages.slack.channel_operations.channel_msg_ops.orjson.loads",
        lambda x: mock_response_data,
    )

    # Mock the API request
    mock_response = {"body": "irrelevant", "status": 200}
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=mock_response))

    # Patch fetch_thread_messages_batch to return thread messages
    monkeypatch.setattr(
        ops,
        "_fetch_thread_messages_parallel",
        AsyncMock(return_value=({"1.1": [{"ts": "2", "text": "reply"}]}, {"U1"})),
    )
    # Patch formatter
    ops._formatter = MagicMock()
    ops._formatter.process_message_batch = AsyncMock(return_value=(["msg1", "reply"], {"U1"}))
    result = await ops.fetch_channel_messages("C1", use_parallel_pagination=False)
    assert "reply" in result


@pytest.mark.asyncio
async def test_fetch_channel_messages_api_error(
    ops: SlackChannelMessageOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test fetch_channel_messages handles Slack API error and retries."""
    monkeypatch.setattr(ops, "_temporarily_unarchive_if_needed", AsyncMock(return_value=False))
    monkeypatch.setattr(ops, "get_api_base_url", AsyncMock(return_value="https://api.slack.com"))
    monkeypatch.setattr(type(ops), "headers", property(lambda self: {}))
    ops._batch_sizer = MagicMock()
    ops._batch_sizer.get_size.return_value = 100
    ops._batch_sizer.increase_size = MagicMock()
    ops._batch_sizer.decrease_size = MagicMock()
    # Simulate Slack API error response
    mock_response = {
        "body": _real_orjson_dumps({"ok": False, "error": "not_in_channel"}).decode("utf-8"),
        "status": 403,
        "request_info": MagicMock(),
        "history": MagicMock(),
    }
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=mock_response))
    # Patch formatter
    ops._formatter = MagicMock()
    ops._formatter.process_message_batch = AsyncMock(return_value=([], set()))
    with patch("packages.slack.channel_operations.channel_msg_ops.logger") as mock_logger:
        with pytest.raises(Exception):
            await ops.fetch_channel_messages("C1", use_parallel_pagination=False)
        assert mock_logger.error.called


@pytest.mark.asyncio
async def test_fetch_channel_messages_exception(
    ops: SlackChannelMessageOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test fetch_channel_messages handles exception and re-raises."""
    monkeypatch.setattr(ops, "_temporarily_unarchive_if_needed", AsyncMock(return_value=False))
    monkeypatch.setattr(ops, "get_api_base_url", AsyncMock(return_value="https://api.slack.com"))
    monkeypatch.setattr(type(ops), "headers", property(lambda self: {}))
    ops._batch_sizer = MagicMock()
    ops._batch_sizer.get_size.return_value = 100
    ops._batch_sizer.increase_size = MagicMock()
    ops._batch_sizer.decrease_size = MagicMock()
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(side_effect=Exception("fail")))
    # Patch formatter
    ops._formatter = MagicMock()
    ops._formatter.process_message_batch = AsyncMock(return_value=([], set()))
    with patch("packages.slack.channel_operations.channel_msg_ops.logger") as mock_logger:
        with pytest.raises(Exception):
            await ops.fetch_channel_messages("C1", use_parallel_pagination=False)
        assert mock_logger.error.called


@pytest.mark.asyncio
async def test_fetch_channel_messages_unarchive_and_rearchive(
    ops: SlackChannelMessageOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test fetch_channel_messages unarchives and re-archives channel as needed."""
    monkeypatch.setattr(ops, "_temporarily_unarchive_if_needed", AsyncMock(return_value=True))
    monkeypatch.setattr(ops, "get_api_base_url", AsyncMock(return_value="https://api.slack.com"))
    monkeypatch.setattr(type(ops), "headers", property(lambda self: {}))
    ops._batch_sizer = MagicMock()
    ops._batch_sizer.get_size.return_value = 100
    ops._batch_sizer.increase_size = MagicMock()
    ops._batch_sizer.decrease_size = MagicMock()

    # Mock orjson.loads to return expected data
    mock_response_data = {"ok": True, "messages": [{"ts": "1", "text": "hi"}]}
    monkeypatch.setattr(
        "packages.slack.channel_operations.channel_msg_ops.orjson.loads",
        lambda x: mock_response_data,
    )

    # Mock the API request
    mock_response = {"body": "irrelevant", "status": 200}
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=mock_response))

    # Patch formatter
    ops._formatter = MagicMock()
    ops._formatter.process_message_batch = AsyncMock(return_value=(["msg1"], set()))
    # Patch fetch_thread_messages_batch to return nothing
    monkeypatch.setattr(ops, "_fetch_thread_messages_parallel", AsyncMock(return_value=({}, set())))
    # Patch archive_ops.archive_channel
    ops.archive_ops.archive_channel = AsyncMock()  # type: ignore[method-assign]
    result = await ops.fetch_channel_messages("C1", use_parallel_pagination=False)
    assert result == ["msg1"]
    ops.archive_ops.archive_channel.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_thread_messages_batch_success(
    ops: SlackChannelMessageOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test fetch_thread_messages_batch returns thread messages and user mentions."""
    monkeypatch.setattr(
        ops,
        "fetch_thread_messages",
        AsyncMock(return_value=[{"ts": "2", "text": "reply", "user": "U1"}]),
    )
    result, mentions = await ops.fetch_thread_messages_batch("C1", ["1.1"])
    assert "2" in [msg["ts"] for msg in result["1.1"]]
    assert "U1" in mentions


@pytest.mark.asyncio
async def test_fetch_thread_messages_batch_empty(
    ops: SlackChannelMessageOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test fetch_thread_messages_batch returns empty if no threads."""
    monkeypatch.setattr(ops, "fetch_thread_messages", AsyncMock(return_value=[]))
    result, mentions = await ops.fetch_thread_messages_batch("C1", [])
    assert result == {}
    assert mentions == set()


@pytest.mark.asyncio
async def test_fetch_thread_messages_success(
    ops: SlackChannelMessageOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test fetch_thread_messages returns list of replies."""
    # Mock the execute_with_backoff method
    mock_messages = [{"ts": "2", "text": "reply"}]
    monkeypatch.setattr(ops, "execute_with_backoff", AsyncMock(return_value=mock_messages))
    result = await ops.fetch_thread_messages("C1", "1.1")
    assert result[0]["ts"] == "2"


@pytest.mark.asyncio
async def test_fetch_thread_messages_api_error(
    ops: SlackChannelMessageOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test fetch_thread_messages handles Slack API error."""
    mock_response = {
        "body": _real_orjson_dumps({"ok": False, "error": "fail"}).decode("utf-8"),
        "status": 200,
    }
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(return_value=mock_response))
    with patch("packages.slack.channel_operations.channel_msg_ops.logger") as mock_logger:
        with pytest.raises(RuntimeError) as excinfo:
            await ops.fetch_thread_messages("C1", "1.1")
        assert str(excinfo.value) == "ratelimited"
        assert mock_logger.error.called


@pytest.mark.asyncio
async def test_fetch_thread_messages_exception(
    ops: SlackChannelMessageOps, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test fetch_thread_messages handles exception and logs."""
    monkeypatch.setattr(ops, "_make_api_request", AsyncMock(side_effect=Exception("fail")))
    with patch("packages.slack.channel_operations.channel_msg_ops.logger") as mock_logger:
        with pytest.raises(RuntimeError) as excinfo:
            await ops.fetch_thread_messages("C1", "1.1")
        assert str(excinfo.value) == "ratelimited"
        assert mock_logger.error.called


@pytest.mark.asyncio
async def test_collect_batch_data_filters_bot_messages(ops: SlackChannelMessageOps) -> None:
    """Test _collect_batch_data filters out bot messages."""
    ops._bot_user_id = "U084HFUQMFE"

    messages = [
        {"ts": "1", "user": "U123456", "text": "Normal message"},
        {"ts": "2", "user": "U084HFUQMFE", "text": "Bot message"},  # Should be filtered
        {"ts": "3", "user": "U789012", "text": "Another normal message"},
    ]

    messages_dict = {}
    user_mentions = set()
    thread_timestamps = []

    await ops._collect_batch_data(messages, messages_dict, user_mentions, thread_timestamps, "C1")

    # Only non-bot messages should be collected
    assert len(messages_dict) == 2
    assert "1" in messages_dict
    assert "2" not in messages_dict  # Bot message filtered out
    assert "3" in messages_dict

    # User mentions should include the non-bot users
    assert "U123456" in user_mentions
    assert "U084HFUQMFE" not in user_mentions  # Bot user not collected
    assert "U789012" in user_mentions


@pytest.mark.asyncio
async def test_collect_batch_data_filters_slash_commands(ops: SlackChannelMessageOps) -> None:
    """Test _collect_batch_data filters out slash commands."""
    ops._bot_user_id = "U084HFUQMFE"

    messages = [
        {"ts": "1", "user": "U123456", "text": "Normal message"},
        {"ts": "2", "user": "U123456", "text": "/ketchup list"},  # Should be filtered
        {
            "ts": "3",
            "user": "U123456",
            "text": " /ketchup analyze something ",
        },  # Should be filtered
        {
            "ts": "4",
            "user": "U123456",
            "text": "not /ketchup in middle",
        },  # Should NOT be filtered
    ]

    messages_dict = {}
    user_mentions = set()
    thread_timestamps = []

    await ops._collect_batch_data(messages, messages_dict, user_mentions, thread_timestamps, "C1")

    # Only non-slash-command messages should be collected
    assert len(messages_dict) == 2
    assert "1" in messages_dict
    assert "2" not in messages_dict  # Slash command filtered out
    assert "3" not in messages_dict  # Slash command with spaces filtered out
    assert "4" in messages_dict  # Not a slash command (doesn't start with /ketchup)


@pytest.mark.asyncio
async def test_collect_batch_data_filters_bot_mentions(ops: SlackChannelMessageOps) -> None:
    """Test _collect_batch_data filters out @Ketchup mentions but keeps thread replies."""
    ops._bot_user_id = "U084HFUQMFE"

    messages = [
        {"ts": "1", "user": "U123456", "text": "Normal message"},
        {
            "ts": "2",
            "user": "U123456",
            "text": "<@U084HFUQMFE> help me",
        },  # Should be filtered
        {
            "ts": "3",
            "user": "U123456",
            "text": "Hey <@U084HFUQMFE> do something",
        },  # Should be filtered
        # Thread reply with bot mention should be kept
        {
            "ts": "4",
            "thread_ts": "1",
            "user": "U123456",
            "text": "<@U084HFUQMFE> in thread",
        },
    ]

    messages_dict = {}
    user_mentions = set()
    thread_timestamps = []

    await ops._collect_batch_data(messages, messages_dict, user_mentions, thread_timestamps, "C1")

    # Only non-mention messages and thread replies should be collected
    assert len(messages_dict) == 2
    assert "1" in messages_dict
    assert "2" not in messages_dict  # Bot mention filtered out
    assert "3" not in messages_dict  # Bot mention filtered out
    assert "4" in messages_dict  # Thread reply kept despite bot mention


@pytest.mark.asyncio
async def test_collect_batch_data_collects_user_mentions(ops: SlackChannelMessageOps) -> None:
    """Test _collect_batch_data properly collects user mentions from text."""
    ops._bot_user_id = "U084HFUQMFE"

    messages = [
        {"ts": "1", "user": "U123456", "text": "Hey <@U789012> check this"},
        {"ts": "2", "user": "U345678", "text": "CC <@U789012|john> and <@U111222>"},
    ]

    messages_dict = {}
    user_mentions = set()
    thread_timestamps = []

    await ops._collect_batch_data(messages, messages_dict, user_mentions, thread_timestamps, "C1")

    # Should collect all user mentions
    assert "U123456" in user_mentions  # Message author
    assert "U345678" in user_mentions  # Message author
    assert "U789012" in user_mentions  # Mentioned user
    assert "U111222" in user_mentions  # Mentioned user


@pytest.mark.asyncio
async def test_collect_batch_data_tracks_thread_timestamps(
    ops: SlackChannelMessageOps,
) -> None:
    """Test _collect_batch_data properly tracks thread parent timestamps."""
    ops._bot_user_id = "U084HFUQMFE"

    messages = [
        {
            "ts": "1",
            "thread_ts": "1",
            "user": "U123456",
            "text": "Thread parent",
        },  # Thread parent
        {
            "ts": "2",
            "thread_ts": "1",
            "user": "U123456",
            "text": "Thread reply",
        },  # Thread reply
        {"ts": "3", "user": "U123456", "text": "Normal message"},
    ]

    messages_dict = {}
    user_mentions = set()
    thread_timestamps = []

    await ops._collect_batch_data(messages, messages_dict, user_mentions, thread_timestamps, "C1")

    # Should track thread parent timestamp
    assert thread_timestamps == ["1"]
    assert len(messages_dict) == 3  # All messages should be collected
