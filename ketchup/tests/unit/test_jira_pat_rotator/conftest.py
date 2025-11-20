"""Shared fixtures for PAT rotator tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_rotation_service():
    """Mock PAT rotation service."""
    return AsyncMock()


@pytest.fixture
def mock_health_service():
    """Mock health status service."""
    return MagicMock()
