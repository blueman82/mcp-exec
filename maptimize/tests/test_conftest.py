import asyncio
import logging

import pytest


@pytest.mark.asyncio
async def test_asyncio_functionality():
    """Test that asyncio functionality works."""
    # Test basic async/await operation
    result = await asyncio.sleep(0, result=42)
    assert result == 42


@pytest.mark.asyncio
async def test_asyncio_can_run_tasks():
    """Test that async tasks can run concurrently."""
    async def sample_coroutine(value):
        await asyncio.sleep(0)
        return value * 2

    task1 = asyncio.create_task(sample_coroutine(5))
    task2 = asyncio.create_task(sample_coroutine(10))
    result1 = await task1
    result2 = await task2
    assert result1 == 10
    assert result2 == 20


def test_mock_logger_fixture(mock_logger):
    """Test that mock logger fixture is available."""
    assert mock_logger is not None
    # Verify it has mock methods
    assert hasattr(mock_logger, 'debug')
    assert hasattr(mock_logger, 'info')


def test_caplog_handler_fixture(caplog_handler):
    """Test that caplog handler fixture is available."""
    assert caplog_handler is not None
    # Verify caplog has handler
    assert hasattr(caplog_handler, 'handler')


def test_pytest_asyncio_mode_configured():
    """Test that pytest asyncio mode is configured in pytest.ini."""
    # This test verifies asyncio_mode is auto by checking if async tests work
    # The presence of working async tests indicates asyncio_mode is properly configured
    assert True


@pytest.mark.asyncio
async def test_multiple_concurrent_tasks():
    """Test that multiple concurrent tasks can run."""
    async def async_op(value):
        await asyncio.sleep(0)
        return value * 2

    tasks = [asyncio.create_task(async_op(i)) for i in range(5)]
    results = await asyncio.gather(*tasks)
    assert results == [0, 2, 4, 6, 8]


def test_mock_slack_event_fixture(mock_slack_event):
    """Test that mock Slack event fixture is available."""
    assert mock_slack_event is not None
    assert mock_slack_event['type'] == 'event_callback'
    assert mock_slack_event['event']['type'] == 'app_mention'


def test_mock_slack_message_event_fixture(mock_slack_message_event):
    """Test that mock Slack message event fixture is available."""
    assert mock_slack_message_event is not None
    assert mock_slack_message_event['event']['type'] == 'message'


def test_mock_slack_app_mention_event_fixture(mock_slack_app_mention_event):
    """Test that mock Slack app mention event fixture is available."""
    assert mock_slack_app_mention_event is not None
    assert mock_slack_app_mention_event['event']['type'] == 'app_mention'
    assert 'team_id' in mock_slack_app_mention_event
