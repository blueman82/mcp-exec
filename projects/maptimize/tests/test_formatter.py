"""Tests for message formatting utilities."""

import pytest

from maptimize.formatter import format_response


@pytest.fixture
def sample_processes_config():
    """Provide sample process configuration for testing."""
    return {
        "Service Review Process": {
            "wiki_url": "https://wiki.corp.adobe.com/display/neolane/Service-Review"
        }
    }


def test_format_response_basic(sample_processes_config):
    """Test formatting with basic process."""
    result = format_response(sample_processes_config)

    assert "Service Review Process" in result
    assert "wiki.corp.adobe.com" in result


def test_format_response_contains_mrkdwn():
    """Test that output uses Slack mrkdwn formatting."""
    processes = {"Process": {"wiki_url": "https://example.com"}}
    result = format_response(processes)

    # Mrkdwn uses * for bold, < > for links
    assert "*" in result or "<" in result


def test_format_response_links_properly_formatted():
    """Test that links are properly formatted in Slack mrkdwn."""
    processes = {"Test Process": {"wiki_url": "https://wiki.example.com/test"}}
    result = format_response(processes)

    # Slack mrkdwn link format: <URL|text>
    assert "<https://wiki.example.com/test|" in result


def test_format_response_empty_process_list():
    """Test handling of empty process list."""
    result = format_response({})

    assert result is not None
    assert len(result) > 0
    assert "No processes" in result or "available" in result.lower()


def test_format_response_multiple_processes():
    """Test formatting with multiple processes."""
    processes = {
        "Process One": {"wiki_url": "https://wiki.example.com/one"},
        "Process Two": {"wiki_url": "https://wiki.example.com/two"},
    }
    result = format_response(processes)

    assert "Process One" in result
    assert "Process Two" in result
    assert result.count("<") >= 2  # At least 2 links


def test_format_response_process_without_wiki_url():
    """Test formatting when process has no wiki_url."""
    processes = {"Process Without URL": {}}
    result = format_response(processes)

    assert "Process Without URL" in result
    # Should still be readable
    assert len(result) > 0


def test_format_response_returns_string():
    """Test that format_response returns a string."""
    processes = {"Test": {"wiki_url": "https://example.com"}}
    result = format_response(processes)

    assert isinstance(result, str)
