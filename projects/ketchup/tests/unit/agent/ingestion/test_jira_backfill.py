"""Tests for JiraBackfillIngestor."""

from unittest.mock import AsyncMock

import pytest

from packages.agent.ingestion.jira_backfill import JiraBackfillIngestor


@pytest.fixture
def mock_deps():
    return {
        "embeddings_client": AsyncMock(),
        "vector_store": AsyncMock(),
        "jira_data_extractor": AsyncMock(),
    }


@pytest.fixture
def ingestor(mock_deps):
    return JiraBackfillIngestor(**mock_deps)


class TestBackfillJira:
    @pytest.mark.asyncio
    async def test_no_ticket_returns_zero(self, ingestor, mock_deps):
        """When no JIRA ticket is found, return 0 documents."""
        mock_deps["jira_data_extractor"].get_jira_context.return_value = None
        result = await ingestor.backfill_jira("C123")
        assert result == 0

    @pytest.mark.asyncio
    async def test_stores_ticket_and_comments(self, ingestor, mock_deps):
        """Ticket summary + 2 comments → 3 documents stored."""
        mock_deps["jira_data_extractor"].get_jira_context.return_value = {
            "ticket_id": "CAMP-1234",
            "source": "channel_metadata",
            "data": {
                "fields": {
                    "summary": "Server is down",
                    "description": "Production server crashed at 3am",
                    "status": {"name": "In Progress"},
                    "priority": {"name": "Critical"},
                    "assignee": {"displayName": "Alice"},
                },
                "comments": [
                    {
                        "id": "c1",
                        "author": "Bob",
                        "created": "2026-03-01",
                        "body": "Investigating now",
                    },
                    {
                        "id": "c2",
                        "author": "Alice",
                        "created": "2026-03-02",
                        "body": "Root cause identified",
                    },
                ],
            },
        }
        mock_deps["embeddings_client"].embed_texts.side_effect = lambda texts: [[0.1] * 1536] * len(
            texts
        )

        result = await ingestor.backfill_jira("C123")

        assert result == 3  # 1 ticket + 2 comments
        mock_deps["vector_store"].add_documents.assert_called_once()
        stored = mock_deps["vector_store"].add_documents.call_args.args[0]

        # Verify document IDs are deterministic
        assert stored[0]["id"] == "C123:jira:CAMP-1234"
        assert stored[1]["id"] == "C123:jira:CAMP-1234:c:c1"
        assert stored[2]["id"] == "C123:jira:CAMP-1234:c:c2"

        # Verify metadata source tags
        for doc in stored:
            assert doc["metadata"]["source"] == "jira"
            assert doc["metadata"]["channel_id"] == "C123"
            assert doc["metadata"]["jira_ticket_id"] == "CAMP-1234"

    @pytest.mark.asyncio
    async def test_empty_comments_only_stores_ticket(self, ingestor, mock_deps):
        """Ticket with no comments → 1 document."""
        mock_deps["jira_data_extractor"].get_jira_context.return_value = {
            "ticket_id": "CAMP-5678",
            "source": "channel_metadata",
            "data": {
                "fields": {
                    "summary": "Minor UI bug",
                    "description": "",
                    "status": {"name": "Open"},
                    "priority": {"name": "Low"},
                    "assignee": None,
                },
                "comments": [],
            },
        }
        mock_deps["embeddings_client"].embed_texts.side_effect = lambda texts: [[0.1] * 1536] * len(
            texts
        )

        result = await ingestor.backfill_jira("C456")
        assert result == 1

    @pytest.mark.asyncio
    async def test_extractor_error_returns_zero(self, ingestor, mock_deps):
        """Graceful degradation when JIRA extractor throws."""
        mock_deps["jira_data_extractor"].get_jira_context.side_effect = Exception(
            "MCP connection failed"
        )
        result = await ingestor.backfill_jira("C123")
        assert result == 0

    @pytest.mark.asyncio
    async def test_ticket_text_includes_key_fields(self, ingestor, mock_deps):
        """Verify the ticket document text contains status, priority, assignee."""
        mock_deps["jira_data_extractor"].get_jira_context.return_value = {
            "ticket_id": "CAMP-999",
            "source": "channel_metadata",
            "data": {
                "fields": {
                    "summary": "Deploy blocker",
                    "description": "Cannot deploy to prod",
                    "status": {"name": "Blocked"},
                    "priority": {"name": "Blocker"},
                    "assignee": {"displayName": "Charlie"},
                },
                "comments": [],
            },
        }
        mock_deps["embeddings_client"].embed_texts.side_effect = lambda texts: [[0.1] * 1536] * len(
            texts
        )

        await ingestor.backfill_jira("C789")

        stored = mock_deps["vector_store"].add_documents.call_args.args[0]
        ticket_text = stored[0]["text"]
        assert "CAMP-999" in ticket_text
        assert "Blocked" in ticket_text
        assert "Blocker" in ticket_text
        assert "Charlie" in ticket_text
        assert "Deploy blocker" in ticket_text
