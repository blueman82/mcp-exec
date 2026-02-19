"""Unit tests for SurveyManager.

Tests CRUD operations, conditional updates, privacy checks.
"""

from unittest.mock import AsyncMock

import pytest

from asksplunk.survey.manager import SurveyManager


class TestSurveyManager:
    """Test SurveyManager operations."""

    @pytest.fixture
    def mock_table(self) -> AsyncMock:
        """Mock aioboto3 DynamoDB table resource."""
        table = AsyncMock()
        table.put_item = AsyncMock()
        table.update_item = AsyncMock()
        table.query = AsyncMock(return_value={"Items": []})
        return table

    @pytest.mark.asyncio
    async def test_create_status(self, mock_table: AsyncMock) -> None:
        """create_status should store survey status with correct fields."""
        manager = SurveyManager(table=mock_table)

        async with manager:
            await manager.create_status("survey_2026_q1", "W7MGASQ2K", "D0123ABC")

        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]

        assert item["thread_id"] == "SURVEY_STATUS#survey_2026_q1#W7MGASQ2K"
        assert item["entity_type"] == "SURVEY_STATUS"
        assert item["survey_id"] == "survey_2026_q1"
        assert item["user_id"] == "W7MGASQ2K"
        assert item["completed"] is False
        assert item["reminders_sent"] == 0
        assert item["last_reminder_at"] is None
        assert item["survey_channel_id"] == "D0123ABC"
        assert "created_at" in item
        assert "ttl" in item

    @pytest.mark.asyncio
    async def test_mark_completed(self, mock_table: AsyncMock) -> None:
        """mark_completed should set completed=True."""
        manager = SurveyManager(table=mock_table)

        async with manager:
            await manager.mark_completed("survey_2026_q1", "W7MGASQ2K")

        mock_table.update_item.assert_called_once()
        call_args = mock_table.update_item.call_args[1]

        assert call_args["Key"]["thread_id"] == "SURVEY_STATUS#survey_2026_q1#W7MGASQ2K"
        assert call_args["ExpressionAttributeValues"][":c"] is True

    @pytest.mark.asyncio
    async def test_mark_completed_idempotent(self, mock_table: AsyncMock) -> None:
        """mark_completed should be safe to call multiple times."""
        manager = SurveyManager(table=mock_table)

        async with manager:
            await manager.mark_completed("survey_2026_q1", "W7MGASQ2K")
            await manager.mark_completed("survey_2026_q1", "W7MGASQ2K")

        assert mock_table.update_item.call_count == 2

    @pytest.mark.asyncio
    async def test_store_response_no_user_id(self, mock_table: AsyncMock) -> None:
        """store_response must NOT include user_id (privacy requirement)."""
        manager = SurveyManager(table=mock_table)

        answers = {
            "question_1": "Very useful",
            "question_2": "Usually correct",
            "question_3": "Multi-turn support",
            "question_4": "Workflow logs",
        }

        async with manager:
            await manager.store_response("survey_2026_q1", answers)

        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]

        # Privacy check
        assert "user_id" not in item
        assert "user" not in item

        assert item["entity_type"] == "SURVEY_RESPONSE"
        assert item["survey_id"] == "survey_2026_q1"
        assert item["question_1"] == "Very useful"
        assert item["question_2"] == "Usually correct"
        assert item["question_3"] == "Multi-turn support"
        assert item["question_4"] == "Workflow logs"
        assert "submitted_at" in item
        assert item["thread_id"].startswith("SURVEY_RESPONSE#survey_2026_q1#")

    @pytest.mark.asyncio
    async def test_store_response_strips_injected_pii(self, mock_table: AsyncMock) -> None:
        """store_response must strip user_id even if caller injects it in answers."""
        manager = SurveyManager(table=mock_table)

        answers = {
            "question_1": "Very useful",
            "user_id": "W7MGASQ2K",  # Injected — must be stripped
            "user": "attacker",
            "email": "evil@example.com",
        }

        async with manager:
            await manager.store_response("survey_2026_q1", answers)

        item = mock_table.put_item.call_args[1]["Item"]
        assert "user_id" not in item
        assert "user" not in item
        assert "email" not in item
        assert item["question_1"] == "Very useful"
        # Reserved fields must not be overwritten
        assert item["entity_type"] == "SURVEY_RESPONSE"
        assert item["survey_id"] == "survey_2026_q1"

    @pytest.mark.asyncio
    async def test_get_pending_users(self, mock_table: AsyncMock) -> None:
        """get_pending_users should query GSI with correct filters."""
        mock_table.query = AsyncMock(
            return_value={
                "Items": [
                    {"user_id": "W7MGASQ2K", "reminders_sent": 0, "survey_channel_id": "D0123"},
                ]
            }
        )
        manager = SurveyManager(table=mock_table)

        async with manager:
            result = await manager.get_pending_users("survey_2026_q1")

        assert len(result) == 1
        assert result[0]["user_id"] == "W7MGASQ2K"

        call_args = mock_table.query.call_args[1]
        assert call_args["IndexName"] == "survey-by-type"
        assert call_args["ExpressionAttributeValues"][":et"] == "SURVEY_STATUS"
        assert call_args["ExpressionAttributeValues"][":sid"] == "survey_2026_q1"
        assert call_args["ExpressionAttributeValues"][":f"] is False

    @pytest.mark.asyncio
    async def test_increment_reminder_success(self, mock_table: AsyncMock) -> None:
        """increment_reminder should return True when condition passes."""
        manager = SurveyManager(table=mock_table)

        async with manager:
            result = await manager.increment_reminder("survey_2026_q1", "W7MGASQ2K")

        assert result is True
        mock_table.update_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_increment_reminder_cooldown_client_error(self, mock_table: AsyncMock) -> None:
        """increment_reminder should return False on ConditionalCheckFailedException via ClientError."""

        class FakeClientError(Exception):
            """Simulates botocore ClientError with response dict."""

            def __init__(self):
                self.response = {"Error": {"Code": "ConditionalCheckFailedException"}}
                super().__init__(
                    "An error occurred (ConditionalCheckFailedException)"
                )

        mock_table.update_item = AsyncMock(side_effect=FakeClientError())

        manager = SurveyManager(table=mock_table)

        async with manager:
            result = await manager.increment_reminder("survey_2026_q1", "W7MGASQ2K")

        assert result is False

    @pytest.mark.asyncio
    async def test_increment_reminder_cooldown_class_name(self, mock_table: AsyncMock) -> None:
        """increment_reminder should also handle exception with matching string."""
        mock_table.update_item = AsyncMock(
            side_effect=Exception("ConditionalCheckFailedException: condition not met")
        )

        manager = SurveyManager(table=mock_table)

        async with manager:
            result = await manager.increment_reminder("survey_2026_q1", "W7MGASQ2K")

        assert result is False

    @pytest.mark.asyncio
    async def test_increment_reminder_raises_on_unexpected_error(
        self, mock_table: AsyncMock
    ) -> None:
        """increment_reminder should re-raise non-conditional errors."""
        mock_table.update_item = AsyncMock(side_effect=RuntimeError("connection error"))

        manager = SurveyManager(table=mock_table)

        async with manager:
            with pytest.raises(RuntimeError, match="connection error"):
                await manager.increment_reminder("survey_2026_q1", "W7MGASQ2K")

    @pytest.mark.asyncio
    async def test_get_results(self, mock_table: AsyncMock) -> None:
        """get_results should aggregate responses and statuses."""
        # First query: responses
        # Second query: statuses
        mock_table.query = AsyncMock(
            side_effect=[
                {
                    "Items": [
                        {
                            "question_1": "Very useful",
                            "question_2": "Usually correct",
                            "question_3": "More features",
                            "question_4": "Workflow logs",
                        },
                        {
                            "question_1": "Very useful",
                            "question_2": "Sometimes correct",
                            "question_3": "Better docs",
                            "question_4": "",
                        },
                    ]
                },
                {
                    "Items": [
                        {"completed": True},
                        {"completed": True},
                        {"completed": False},
                    ]
                },
            ]
        )

        manager = SurveyManager(table=mock_table)

        async with manager:
            results = await manager.get_results("survey_2026_q1")

        assert results["survey_id"] == "survey_2026_q1"
        assert results["total_sent"] == 3
        assert results["total_responses"] == 2
        assert results["total_completed"] == 2
        assert results["completion_rate"] == 66.7
        assert results["answers"]["question_1"]["Very useful"] == 2

    @pytest.mark.asyncio
    async def test_get_active_survey_ids(self, mock_table: AsyncMock) -> None:
        """get_active_survey_ids should return distinct survey IDs."""
        mock_table.query = AsyncMock(
            return_value={
                "Items": [
                    {"survey_id": "survey_2026_q1"},
                    {"survey_id": "survey_2026_q1"},
                    {"survey_id": "survey_2026_q2"},
                ]
            }
        )
        manager = SurveyManager(table=mock_table)

        async with manager:
            ids = await manager.get_active_survey_ids()

        assert sorted(ids) == ["survey_2026_q1", "survey_2026_q2"]

    @pytest.mark.asyncio
    async def test_context_manager_raises_outside_context(self) -> None:
        """SurveyManager should raise RuntimeError if used outside context manager."""
        manager = SurveyManager()

        with pytest.raises(RuntimeError, match="async context manager"):
            await manager.create_status("s", "u", "c")
