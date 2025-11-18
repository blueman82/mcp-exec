"""
test_logging.py

Unit tests for the setup_logger function in packages.core.logging.

Covers:
- Logger creation, level, handler, and propagation settings

All tests follow the Ketchup Slack Bot test plan and cursor rules.
"""

import logging

import pytest

from packages.core.logging import setup_logger

pytestmark = pytest.mark.unit


@pytest.mark.unit
def test_setup_logger_creates_logger() -> None:
    """Test setup_logger returns a logger with correct name and level.

    Verifies logger name, level, handler presence, and propagation settings.
    """
    logger = setup_logger("test_logger", level=logging.DEBUG)
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_logger"
    assert logger.level == logging.DEBUG
    # Should have at least one handler
    assert logger.hasHandlers()
    # Should not propagate
    assert not logger.propagate
