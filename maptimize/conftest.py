import asyncio
import logging
import sys
from pathlib import Path
from typing import Generator

import pytest

# Add src/ to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))


@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Provide event loop for async tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture
def mock_logger(mocker):
    """Provide mock logger for testing log messages."""
    return mocker.patch("structlog.get_logger")


@pytest.fixture
def caplog_handler(caplog):
    """Provide caplog with structured logging handler."""
    caplog.set_level(logging.DEBUG)
    return caplog
