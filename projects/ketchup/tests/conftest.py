"""
Tests directory conftest.py - imports fixtures from root conftest.py.

The main pytest configuration and fixtures are defined in the project root's
conftest.py. This file exists for backward compatibility when running pytest
directly from the tests/ directory.

All fixtures (AWS mocking, mock reset, async cleanup) are imported from the
root conftest.py via pytest's automatic parent directory fixture discovery.
"""

# Pytest automatically discovers conftest.py files in parent directories,
# so fixtures from ../conftest.py are available without explicit import.
# This file can contain any tests/-specific fixtures if needed.
