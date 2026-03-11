"""Tests for conversation data models."""

from packages.agent.conversation.models import (
    AgentThread,
    ConversationTurn,
    MessageWatermark,
)


class TestConversationTurn:
    def test_create_user_turn(self):
        turn = ConversationTurn(
            channel_id="C123",
            thread_ts="1234.5678",
            timestamp="1710000000000",
            role="user",
            content="hello",
            user_id="U456",
        )
        assert turn.role == "user"
        assert turn.user_id == "U456"

    def test_create_assistant_turn(self):
        turn = ConversationTurn(
            channel_id="C123",
            thread_ts="1234.5678",
            timestamp="1710000000000",
            role="assistant",
            content="response",
        )
        assert turn.user_id is None


class TestAgentThread:
    def test_default_status(self):
        thread = AgentThread(
            channel_id="C123",
            thread_ts="1234.5678",
            created_at=1710000000,
            last_active_at=1710000000,
        )
        assert thread.status == "active"


class TestMessageWatermark:
    def test_defaults(self):
        wm = MessageWatermark(
            channel_id="C123",
            latest_ingested_ts="0",
        )
        assert wm.backfill_complete is False
        assert wm.total_ingested == 0
        assert wm.backfill_started_at is None
