"""Tests for module structure and importability."""

import importlib
import sys

import pytest

MODULES = ["config", "bot", "handlers", "formatter", "utils"]


@pytest.fixture(autouse=True)
def mock_slack_tokens(mocker):
    """Mock get_slack_tokens and slack-bolt App for all tests in this module."""
    mocker.patch(
        "maptimize.config.get_slack_tokens",
        return_value=("xoxb-test-token", "xapp-test-token", "test-signing-secret")
    )
    # Mock slack-bolt App to prevent auth.test verification
    from unittest.mock import MagicMock
    mock_app = MagicMock()
    mock_app._listeners = []
    mocker.patch("slack_bolt.app.App", return_value=mock_app)


@pytest.mark.parametrize("module_name", MODULES)
def test_module_importable(module_name):
    """Test that module can be imported."""
    module = importlib.import_module(f"maptimize.{module_name}")
    assert module is not None


@pytest.mark.parametrize("module_name", MODULES)
def test_module_has_docstring(module_name):
    """Test that module has a docstring."""
    module = importlib.import_module(f"maptimize.{module_name}")
    assert module.__doc__ is not None
    assert len(module.__doc__.strip()) > 0
