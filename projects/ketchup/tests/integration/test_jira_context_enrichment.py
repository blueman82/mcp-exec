"""
test_jira_context_enrichment.py

Integration test to verify JIRA context is being added to OpenAI messages.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.ai.core.openai_handler import OpenAIHandler
from packages.integrations.jira_data_extractor import JIRADataExtractor

pytestmark = pytest.mark.asyncio


@pytest.mark.integration
async def test_openai_handler_enriches_with_jira_context():
    """Test that OpenAI handler properly enriches messages with JIRA context."""

    # Create mock dependencies
    mock_token_tracker = MagicMock()
    mock_secrets_manager = AsyncMock()
    mock_channel_info_ops = AsyncMock()
    mock_channel_msg_ops = AsyncMock()
    mock_channel_ops = AsyncMock()

    # Create mock JIRA extractor
    mock_jira_extractor = AsyncMock(spec=JIRADataExtractor)
    mock_jira_extractor.get_jira_context = AsyncMock(
        return_value={
            "ticket_id": "CAMP-12345",
            "data": {
                "fields": {
                    "summary": "Test Issue Summary",
                    "status": {"name": "In Progress"},
                    "priority": {"name": "High"},
                }
            },
        }
    )

    # Create OpenAI handler with JIRA extractor
    handler = OpenAIHandler(
        token_tracker=mock_token_tracker,
        secrets_manager=mock_secrets_manager,
        channel_info_ops=mock_channel_info_ops,
        channel_msg_ops=mock_channel_msg_ops,
        channel_ops=mock_channel_ops,
        jira_extractor=mock_jira_extractor,
    )

    # Test messages
    test_messages = [{"role": "user", "content": "What is the status of CAMP-12345?"}]

    # Enrich messages
    enriched_messages = await handler._enrich_with_jira_context(test_messages, "C123456")

    # Verify JIRA context was called
    mock_jira_extractor.get_jira_context.assert_called_once_with(
        "C123456", ["What is the status of CAMP-12345?"]
    )

    # Verify enrichment
    assert len(enriched_messages) == 2  # Original + JIRA context
    assert enriched_messages[0]["role"] == "system"
    assert "JIRA Context Information" in enriched_messages[0]["content"]
    assert "CAMP-12345" in enriched_messages[0]["content"]
    assert "Test Issue Summary" in enriched_messages[0]["content"]
    assert "In Progress" in enriched_messages[0]["content"]
    assert "High" in enriched_messages[0]["content"]

    # Original message should be second
    assert enriched_messages[1] == test_messages[0]


@pytest.mark.integration
async def test_openai_handler_works_without_jira():
    """Test that OpenAI handler works fine without JIRA extractor."""

    # Create mock dependencies
    mock_token_tracker = MagicMock()
    mock_secrets_manager = AsyncMock()
    mock_channel_info_ops = AsyncMock()
    mock_channel_msg_ops = AsyncMock()
    mock_channel_ops = AsyncMock()

    # Create OpenAI handler WITHOUT JIRA extractor
    handler = OpenAIHandler(
        token_tracker=mock_token_tracker,
        secrets_manager=mock_secrets_manager,
        channel_info_ops=mock_channel_info_ops,
        channel_msg_ops=mock_channel_msg_ops,
        channel_ops=mock_channel_ops,
        jira_extractor=None,  # No JIRA extractor
    )

    # Test messages
    test_messages = [{"role": "user", "content": "What is the status of CAMP-12345?"}]

    # Try to enrich messages
    enriched_messages = await handler._enrich_with_jira_context(test_messages, "C123456")

    # Should return original messages unchanged
    assert enriched_messages == test_messages
    assert len(enriched_messages) == 1
