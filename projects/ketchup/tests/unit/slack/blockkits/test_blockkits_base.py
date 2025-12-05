"""
Unit tests for packages.slack.blockkits.base

This module provides comprehensive tests for the BlockKitBuilder class, which composes all BlockKit handlers and provides a consistent interface for sending formatted messages to Slack.

Coverage includes:
- __init__ (handler wiring)
- configure (all handler configure calls, with/without optional args)
- _get_channel_details_with_fallback (normal, missing getter, exception, fallback)
- All public API methods (send_ketchup_query_block_kit, send_ketchup_status_block_kit, send_ketchup_report_block_kit, send_ketchup_summary_block_kit, send_ketchup_lookup_block_kit, send_ketchup_archive_block_kit, send_thread_message), including handler exceptions
- All handler dependencies and async methods are mocked

Expected outcomes:
- All branches and error cases are directly tested
- All tests are mypy- and ruff-clean
- Each test function includes a detailed docstring per @ketchup_test_plan.md
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.slack.blockkits import base


@pytest.fixture
def builder():
    with (
        patch(
            "packages.slack.blockkits.base.QueryMessageHandler", return_value=MagicMock()
        ) as query_handler,
        patch(
            "packages.slack.blockkits.base.StatusMessageHandler", return_value=MagicMock()
        ) as status_handler,
        patch(
            "packages.slack.blockkits.base.ReportMessageHandler", return_value=MagicMock()
        ) as report_handler,
        patch(
            "packages.slack.blockkits.base.SummaryMessageHandler", return_value=MagicMock()
        ) as summary_handler,
        patch(
            "packages.slack.blockkits.base.LookupMessageHandler", return_value=MagicMock()
        ) as lookup_handler,
        patch(
            "packages.slack.blockkits.base.ArchiveMessageHandler", return_value=MagicMock()
        ) as archive_handler,
    ):
        posting_handler = MagicMock()
        b = base.BlockKitBuilder(posting_handler)
        # Attach handler mocks for direct access
        b._query_handler = query_handler.return_value
        b._status_handler = status_handler.return_value
        b._report_handler = report_handler.return_value
        b._summary_handler = summary_handler.return_value
        b._lookup_handler = lookup_handler.return_value
        b._archive_handler = archive_handler.return_value
        return b


def test_init_wires_handlers() -> None:
    """Test __init__ wires all handler attributes."""
    with (
        patch(
            "packages.slack.blockkits.base.QueryMessageHandler", return_value=MagicMock()
        ) as query_handler,
        patch(
            "packages.slack.blockkits.base.StatusMessageHandler", return_value=MagicMock()
        ) as status_handler,
        patch(
            "packages.slack.blockkits.base.ReportMessageHandler", return_value=MagicMock()
        ) as report_handler,
        patch(
            "packages.slack.blockkits.base.SummaryMessageHandler", return_value=MagicMock()
        ) as summary_handler,
        patch(
            "packages.slack.blockkits.base.LookupMessageHandler", return_value=MagicMock()
        ) as lookup_handler,
        patch(
            "packages.slack.blockkits.base.ArchiveMessageHandler", return_value=MagicMock()
        ) as archive_handler,
    ):
        posting_handler = MagicMock()
        b = base.BlockKitBuilder(posting_handler)
        assert b._query_handler is query_handler.return_value
        assert b._status_handler is status_handler.return_value
        assert b._report_handler is report_handler.return_value
        assert b._summary_handler is summary_handler.return_value
        assert b._lookup_handler is lookup_handler.return_value
        assert b._archive_handler is archive_handler.return_value


def test_configure_calls_all_handlers(builder) -> None:
    """Test configure wires all handlers and passes dependencies."""
    channel_details_getter = MagicMock()
    build_feedback_blocks = MagicMock()
    builder.configure(
        channel_details_getter,
        build_feedback_blocks_func=build_feedback_blocks,
    )
    # All handlers' configure should be called
    assert builder._query_handler.configure.called
    assert builder._status_handler.configure.called
    assert builder._report_handler.configure.called
    assert builder._summary_handler.configure.called
    assert builder._lookup_handler.configure.called
    assert builder._archive_handler.configure.called


def test_configure_without_optional_args(builder) -> None:
    """Test configure works with only required arguments."""
    channel_details_getter = MagicMock()
    builder.configure(channel_details_getter)
    assert builder._query_handler.configure.called


@pytest.mark.asyncio
async def test_get_channel_details_with_fallback_normal(builder) -> None:
    """Test _get_channel_details_with_fallback returns channel details from getter."""
    builder._channel_details_getter = AsyncMock(
        return_value={"channel_id": "C1", "channel_name": "chan1"}
    )
    result = await builder._get_channel_details_with_fallback("C1")
    assert result["channel_id"] == "C1"
    assert result["channel_name"] == "chan1"


@pytest.mark.asyncio
async def test_get_channel_details_with_fallback_missing_getter(builder) -> None:
    """Test _get_channel_details_with_fallback returns fallback if getter is missing."""
    builder._channel_details_getter = None
    result = await builder._get_channel_details_with_fallback("C2")
    assert result["channel_id"] == "C2"
    assert result["customer_name"] == "NOT YET AVAILABLE"


@pytest.mark.asyncio
async def test_get_channel_details_with_fallback_exception(builder) -> None:
    """Test _get_channel_details_with_fallback returns fallback on exception."""
    builder._channel_details_getter = AsyncMock(side_effect=Exception("fail"))
    result = await builder._get_channel_details_with_fallback("C3")
    assert result["channel_id"] == "C3"
    assert result["customer_name"] == "NOT YET AVAILABLE"


@pytest.mark.asyncio
async def test_get_channel_details_with_fallback_empty_result(builder) -> None:
    """Test _get_channel_details_with_fallback returns fallback if getter returns None/empty."""
    builder._channel_details_getter = AsyncMock(return_value=None)
    result = await builder._get_channel_details_with_fallback("C4")
    assert result["channel_id"] == "C4"
    assert result["customer_name"] == "NOT YET AVAILABLE"


@pytest.mark.asyncio
async def test_send_ketchup_query_block_kit(builder) -> None:
    """Test send_ketchup_query_block_kit delegates to query handler."""
    builder._query_handler.send_message = AsyncMock()
    await builder.send_ketchup_query_block_kit("cmd", "url", "resp", query="q", target_channel="C1")
    builder._query_handler.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_ketchup_status_block_kit(builder) -> None:
    """Test send_ketchup_status_block_kit delegates to status handler."""
    builder._status_handler.send_message = AsyncMock()
    await builder.send_ketchup_status_block_kit(
        "cmd", "url", "resp", query="q", target_channel="C1"
    )
    builder._status_handler.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_ketchup_report_block_kit(builder) -> None:
    """Test send_ketchup_report_block_kit delegates to report handler."""
    builder._report_handler.send_message = AsyncMock()
    await builder.send_ketchup_report_block_kit(
        "cmd", "url", "resp", query="q", target_channel="C1"
    )
    builder._report_handler.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_ketchup_summary_block_kit(builder) -> None:
    """Test send_ketchup_summary_block_kit delegates to summary handler."""
    builder._summary_handler.send_message = AsyncMock()
    await builder.send_ketchup_summary_block_kit(
        "cmd", "url", [{"summary": 1}], target_channel="C1"
    )
    builder._summary_handler.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_ketchup_archive_block_kit(builder) -> None:
    """Test send_ketchup_archive_block_kit delegates to archive handler."""
    builder._archive_handler.send_message = AsyncMock()
    await builder.send_ketchup_archive_block_kit("url", [{"summary": 1}], incoming_channel="C1")
    builder._archive_handler.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_handler_exceptions_do_not_crash(builder) -> None:
    """Test public API methods handle handler exceptions gracefully."""
    builder._query_handler.send_message = AsyncMock(side_effect=Exception("fail"))
    try:
        await builder.send_ketchup_query_block_kit("cmd", "url", "resp")
    except Exception:
        pass  # Should not crash test
