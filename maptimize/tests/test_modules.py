"""Tests for module structure and importability."""

import importlib

import pytest


MODULES = ["config", "bot", "handlers", "formatter", "utils"]


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
