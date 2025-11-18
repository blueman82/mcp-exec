"""
test_jira_enrichment_e2e.py

End-to-end test showing how JIRA context enrichment works with real commands.
This demonstrates Option 1 implementation in action.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.asyncio


@pytest.mark.integration
async def test_status_command_with_jira_enrichment():
    """Test that status command gets enriched with JIRA context."""

    # This test demonstrates the flow:
    # 1. User runs /ketchup status in a channel
    # 2. OpenAI handler prepares messages for the status prompt
    # 3. JIRA extractor finds related ticket (e.g., from channel metadata)
    # 4. OpenAI receives both the status request AND JIRA context
    # 5. AI can provide status that references the JIRA ticket

    from packages.ai.core.openai_handler import OpenAIHandler
    from packages.integrations.jira_data_extractor import JIRADataExtractor

    # Mock JIRA data that would come from the channel
    mock_jira_data = {
        "ticket_id": "CAMP-59130",
        "data": {
            "fields": {
                "summary": "{L5} Missing Security Related Headers",
                "status": {"name": "Open"},
                "priority": {"name": "L5"},
                "description": "Security headers are missing from the application",
                "assignee": {"displayName": "John Doe"},
                "created": "2025-06-16T16:17:46.000+0000",
            }
        },
    }

    # Create mock JIRA extractor
    mock_jira_extractor = AsyncMock(spec=JIRADataExtractor)
    mock_jira_extractor.get_jira_context = AsyncMock(return_value=mock_jira_data)

    # Create mock dependencies
    mock_deps = {
        "token_tracker": MagicMock(),
        "secrets_manager": AsyncMock(),
        "channel_info_ops": AsyncMock(),
        "channel_msg_ops": AsyncMock(),
        "channel_ops": AsyncMock(),
    }

    # Create handler with JIRA
    handler = OpenAIHandler(**mock_deps, jira_extractor=mock_jira_extractor)

    # Simulate status command messages
    status_messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant providing channel status.",
        },
        {
            "role": "user",
            "content": "Please provide the current status of this channel including any active issues.",
        },
    ]

    # Enrich with JIRA context
    enriched = await handler._enrich_with_jira_context(status_messages, "C123456")

    # Verify the enrichment
    assert len(enriched) == 3  # JIRA context + 2 original messages

    # Check JIRA context is first
    jira_msg = enriched[0]
    assert jira_msg["role"] == "system"
    assert "JIRA Context Information" in jira_msg["content"]
    assert "CAMP-59130" in jira_msg["content"]
    assert "Missing Security Related Headers" in jira_msg["content"]

    # Original messages follow
    assert enriched[1] == status_messages[0]
    assert enriched[2] == status_messages[1]

    print("\n✅ Status command would receive:")
    print("   - JIRA Ticket: CAMP-59130")
    print(f"   - Summary: {mock_jira_data['data']['fields']['summary']}")
    print(f"   - Status: {mock_jira_data['data']['fields']['status']['name']}")
    print("\n   The AI can now provide status that includes this JIRA context!")


@pytest.mark.integration
async def test_query_command_with_jira_enrichment():
    """Test query command finding JIRA tickets in messages."""

    # This demonstrates finding JIRA tickets mentioned in channel messages
    from packages.ai.core.openai_handler import OpenAIHandler
    from packages.integrations.jira_data_extractor import JIRADataExtractor

    # Mock finding JIRA ticket from message text
    mock_jira_extractor = AsyncMock(spec=JIRADataExtractor)
    mock_jira_extractor.get_jira_context = AsyncMock(
        return_value={
            "ticket_id": "PROJ-123",
            "data": {
                "fields": {
                    "summary": "Performance degradation in production",
                    "status": {"name": "Investigating"},
                    "priority": {"name": "P1"},
                }
            },
        }
    )

    # Query messages that mention a ticket
    query_messages = [
        {
            "role": "user",
            "content": "Can you check the messages about PROJ-123 and summarize the investigation?",
        }
    ]

    handler = OpenAIHandler(
        token_tracker=MagicMock(),
        secrets_manager=AsyncMock(),
        channel_info_ops=AsyncMock(),
        channel_msg_ops=AsyncMock(),
        channel_ops=AsyncMock(),
        jira_extractor=mock_jira_extractor,
    )

    enriched = await handler._enrich_with_jira_context(query_messages, "C789012")

    # JIRA extractor would have been called with the message text
    mock_jira_extractor.get_jira_context.assert_called_once_with(
        "C789012",
        ["Can you check the messages about PROJ-123 and summarize the investigation?"],
    )

    # AI now has both the query AND the JIRA context
    assert len(enriched) == 2
    assert "Performance degradation in production" in enriched[0]["content"]
    assert "Investigating" in enriched[0]["content"]

    print("\n✅ Query command would receive JIRA context for PROJ-123")
    print("   AI can now provide investigation summary with full ticket context!")
