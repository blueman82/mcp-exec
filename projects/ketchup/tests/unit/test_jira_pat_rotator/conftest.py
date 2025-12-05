"""Shared fixtures for PAT rotator tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_rotation_service():
    """Mock PAT rotation service."""
    return AsyncMock()


@pytest.fixture
def mock_health_service():
    """Mock health status service."""
    return MagicMock()
