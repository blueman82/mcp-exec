import asyncio
import logging
import sys
from pathlib import Path
from typing import Generator

import pytest

# Add src/ to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))


@pytest.fixture
def mock_logger(mocker):
    """Provide mock logger for testing log messages."""
    logger_mock = mocker.MagicMock()
    mocker.patch("logging.getLogger", return_value=logger_mock)
    return logger_mock


@pytest.fixture
def caplog_handler(caplog):
    """Provide caplog with structured logging handler."""
    caplog.set_level(logging.DEBUG)
    return caplog


@pytest.fixture
def mock_slack_event():
    """Provide mock Slack event for testing."""
    return {
        'type': 'event_callback',
        'event': {
            'type': 'app_mention',
            'user': 'U123456',
            'text': '<@U789> hello',
            'ts': '1234567890.000001'
        }
    }


@pytest.fixture
def mock_slack_message_event():
    """Provide mock Slack message event for testing."""
    return {
        'type': 'event_callback',
        'event': {
            'type': 'message',
            'user': 'U123456',
            'text': 'test message',
            'ts': '1234567890.000002',
            'channel': 'C123456'
        }
    }


@pytest.fixture
def mock_slack_app_mention_event():
    """Provide mock Slack app mention event for testing."""
    return {
        'type': 'event_callback',
        'event': {
            'type': 'app_mention',
            'user': 'U123456',
            'text': '<@U789> what is the status',
            'ts': '1234567890.000003',
            'channel': 'C123456'
        },
        'team_id': 'T123456'
    }
