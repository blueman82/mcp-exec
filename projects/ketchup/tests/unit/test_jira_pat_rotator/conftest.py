"""Shared fixtures for PAT rotator tests."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure AWS region is set for all tests in this module
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-west-1")
os.environ.setdefault("AWS_REGION", "eu-west-1")


@pytest.fixture(autouse=True)
def mock_boto3_client():
    """Auto-mock boto3 client to prevent real AWS calls."""
    mock_client = MagicMock()
    mock_client.get_secret_value.return_value = {
        "SecretString": '{"JIRA_PAT": "test-pat", "JIRA_PAT_EXPIRY": "2025-12-31T00:00:00Z"}'
    }
    mock_client.update_secret.return_value = {}
    
    with patch("boto3.client", return_value=mock_client):
        with patch("boto3.Session") as mock_session:
            mock_session.return_value.client.return_value = mock_client
            yield mock_client


@pytest.fixture
def mock_rotation_service():
    """Mock PAT rotation service."""
    return AsyncMock()


@pytest.fixture
def mock_health_service():
    """Mock health status service."""
    return MagicMock()
