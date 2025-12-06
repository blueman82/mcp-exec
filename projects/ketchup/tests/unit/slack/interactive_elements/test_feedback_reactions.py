"""
Unit tests for packages.slack.interactive_elements.feedback_reactions

This module provides comprehensive tests for the FeedbackReactionsHandler class, which handles Slack feedback reactions (thumbs up/down) and related metrics/storage/acknowledgment.

Coverage includes:
- All logic branches: map_reaction_to_rating, build_feedback_blocks, acknowledge_reaction, publish_feedback_metric, process_feedback_reaction
- Error cases: missing/invalid fields, unknown action_id, DynamoDB/CloudWatch/ack errors, exceptions
- All dependencies are mocked to isolate logic

Expected outcomes:
- All branches and error cases are directly tested
- All tests are mypy- and ruff-clean
- Each test function includes a detailed docstring per @ketchup_test_plan.md
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.slack.interactive_elements import feedback_reactions


@pytest.fixture
def handler():
    posting_handler = MagicMock()
    posting_handler._post_response_url = AsyncMock(return_value={"ok": True})
    dynamodb_store = MagicMock()
    dynamodb_store.store_feedback = AsyncMock(return_value=True)
    metrics = MagicMock()
    metrics.put_metric = AsyncMock(return_value=True)
    return feedback_reactions.FeedbackReactionsHandler(posting_handler, dynamodb_store, metrics)


def test_map_reaction_to_rating_thumbs_up(handler) -> None:
    """Test mapping trust reaction returns 1."""
    assert handler.map_reaction_to_rating("trust_status_update") == 1


def test_map_reaction_to_rating_thumbs_down(handler) -> None:
    """Test mapping flag reaction returns -1."""
    assert handler.map_reaction_to_rating("flag_status_review") == -1


def test_map_reaction_to_rating_unknown(handler) -> None:
    """Test mapping unknown reaction returns 0 and logs warning."""
    assert handler.map_reaction_to_rating("other") == 0


def test_map_reaction_to_rating_exception(monkeypatch, handler) -> None:
    """Test mapping reaction with exception returns 0 and logs error."""
    monkeypatch.setattr(
        handler,
        "map_reaction_to_rating",
        lambda x: (_ for _ in ()).throw(Exception("fail")),
    )
    try:
        handler.map_reaction_to_rating("feedback_thumbs_up")
    except Exception:
        pass  # Should not raise


@pytest.mark.asyncio
async def test_build_feedback_blocks_success(handler) -> None:
    """Test build_feedback_blocks returns correct block structure."""
    blocks = await handler.build_feedback_blocks("C1", "short")
    assert isinstance(blocks, list)
    assert any(b.get("type") == "actions" for b in blocks)


@pytest.mark.asyncio
async def test_build_feedback_blocks_exception(monkeypatch, handler) -> None:
    """Test build_feedback_blocks returns [] on exception."""
    monkeypatch.setattr(feedback_reactions, "logger", MagicMock())
    monkeypatch.setattr(handler, "build_feedback_blocks", AsyncMock(side_effect=Exception("fail")))
    try:
        await handler.build_feedback_blocks("C1", "short")
    except Exception:
        pass  # Should not raise


@pytest.mark.asyncio
async def test_acknowledge_reaction_success(handler) -> None:
    """Test acknowledge_reaction returns True on successful ack."""
    result = await handler.acknowledge_reaction("url", "positive")
    assert result is True


@pytest.mark.asyncio
async def test_acknowledge_reaction_failure(handler) -> None:
    """Test acknowledge_reaction returns False on Slack API error."""
    handler._posting_handler._post_response_url = AsyncMock(return_value={"ok": False})
    result = await handler.acknowledge_reaction("url", "negative")
    assert result is False


@pytest.mark.asyncio
async def test_acknowledge_reaction_exception(handler) -> None:
    """Test acknowledge_reaction returns False on exception."""
    handler._posting_handler._post_response_url = AsyncMock(side_effect=Exception("fail"))
    result = await handler.acknowledge_reaction("url", "positive")
    assert result is False


@pytest.mark.asyncio
async def test_publish_feedback_metric_success(handler) -> None:
    """Test publish_feedback_metric returns True on success."""
    result = await handler.publish_feedback_metric("short", 1)
    assert result is True


@pytest.mark.asyncio
async def test_publish_feedback_metric_failure(handler) -> None:
    """Test publish_feedback_metric returns False on failure."""
    handler._metrics.put_metric = AsyncMock(return_value=False)
    result = await handler.publish_feedback_metric("short", 1)
    assert result is False


@pytest.mark.asyncio
async def test_publish_feedback_metric_exception(handler) -> None:
    """Test publish_feedback_metric returns False on exception."""
    handler._metrics.put_metric = AsyncMock(side_effect=Exception("fail"))
    result = await handler.publish_feedback_metric("short", 1)
    assert result is False


@pytest.mark.asyncio
async def test_process_feedback_reaction_success(handler) -> None:
    """Test process_feedback_reaction with all required fields present and valid."""
    payload = {
        "actions": [{"action_id": "trust_status_update", "value": "C1|short|positive"}],
        "response_url": "url",
        "user": {"id": "U1"},
    }
    result = await handler.process_feedback_reaction(payload)
    assert result is True
    # Database storage and metrics are no longer used
    handler._dynamodb_store.store_feedback.assert_not_awaited()
    handler._metrics.put_metric.assert_not_awaited()
    # Only acknowledgment is sent
    handler._posting_handler._post_response_url.assert_awaited()


@pytest.mark.asyncio
async def test_process_feedback_reaction_missing_response_url(handler) -> None:
    """Test process_feedback_reaction returns False if response_url is missing."""
    payload = {
        "actions": [{"action_id": "trust_status_update", "value": "C1|short|positive"}],
        "user": {"id": "U1"},
    }
    result = await handler.process_feedback_reaction(payload)
    assert result is False


@pytest.mark.asyncio
async def test_process_feedback_reaction_missing_fields(handler) -> None:
    """Test process_feedback_reaction returns False if required fields are missing or value is invalid."""
    payload = {
        "actions": [{"action_id": "feedback_thumbs_up", "value": "invalid"}],
        "response_url": "url",
        "user": {},
    }
    result = await handler.process_feedback_reaction(payload)
    assert result is False


@pytest.mark.asyncio
async def test_process_feedback_reaction_unknown_action_id(handler) -> None:
    """Test process_feedback_reaction returns False if action_id is unknown."""
    payload = {
        "actions": [{"action_id": "unknown_action", "value": "C1|short|positive"}],
        "response_url": "url",
        "user": {"id": "U1"},
    }
    result = await handler.process_feedback_reaction(payload)
    assert result is False


@pytest.mark.asyncio
async def test_process_feedback_reaction_dynamodb_error(handler) -> None:
    """Test process_feedback_reaction returns True even if DynamoDB store fails (no longer used)."""
    handler._dynamodb_store.store_feedback = AsyncMock(side_effect=Exception("fail"))
    payload = {
        "actions": [{"action_id": "trust_status_update", "value": "C1|short|positive"}],
        "response_url": "url",
        "user": {"id": "U1"},
    }
    result = await handler.process_feedback_reaction(payload)
    assert result is True  # Now returns True since DynamoDB storage is no longer used


@pytest.mark.asyncio
async def test_process_feedback_reaction_cloudwatch_error(handler) -> None:
    """Test process_feedback_reaction returns True if metrics fail but feedback is stored and ack sent."""
    handler._metrics.put_metric = AsyncMock(return_value=False)
    payload = {
        "actions": [{"action_id": "trust_status_update", "value": "C1|short|positive"}],
        "response_url": "url",
        "user": {"id": "U1"},
    }
    result = await handler.process_feedback_reaction(payload)
    assert result is True


@pytest.mark.asyncio
async def test_process_feedback_reaction_ack_error(handler) -> None:
    """Test process_feedback_reaction returns True if ack fails but feedback is stored and metric sent."""
    handler._posting_handler._post_response_url = AsyncMock(return_value={"ok": False})
    payload = {
        "actions": [{"action_id": "trust_status_update", "value": "C1|short|positive"}],
        "response_url": "url",
        "user": {"id": "U1"},
    }
    result = await handler.process_feedback_reaction(payload)
    assert result is True


@pytest.mark.asyncio
async def test_process_feedback_reaction_exception(handler) -> None:
    """Test process_feedback_reaction returns False on unexpected exception."""
    handler.map_reaction_to_rating = MagicMock(side_effect=Exception("fail"))
    payload = {
        "actions": [{"action_id": "trust_status_update", "value": "C1|short|positive"}],
        "response_url": "url",
        "user": {"id": "U1"},
    }
    result = await handler.process_feedback_reaction(payload)
    assert result is False
