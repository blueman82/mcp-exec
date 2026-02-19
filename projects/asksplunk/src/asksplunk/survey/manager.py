"""DynamoDB survey manager for feedback collection.

Implements async CRUD operations for survey status tracking and anonymous
response storage. Privacy-first: responses stored without user IDs.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any

import structlog

logger = structlog.get_logger()

# 90 days TTL for survey records
_SURVEY_TTL_DAYS = 90


class SurveyManager:
    """Manages survey status and responses in DynamoDB.

    Tracks per-user completion status (with user ID) and stores
    anonymous responses (without user ID) for privacy.

    Must be used as async context manager:
        async with SurveyManager() as manager:
            await manager.create_status(...)
    """

    def __init__(
        self,
        table: Any | None = None,
        table_name: str = "splunk-bot-sessions",
        region: str = "eu-west-1",
    ) -> None:
        self.table_name = table_name
        self.region = region
        self._table: Any | None = table
        self._resource_context: Any | None = None

    async def __aenter__(self) -> "SurveyManager":
        if not self._table:
            import aioboto3

            session = aioboto3.Session()
            self._resource_context = session.resource("dynamodb", region_name=self.region)
            resource = await self._resource_context.__aenter__()
            self._table = await resource.Table(self.table_name)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if self._resource_context:
            await self._resource_context.__aexit__(exc_type, exc_val, exc_tb)
            self._table = None
            self._resource_context = None

    async def _get_table(self) -> Any:
        if not self._table:
            raise RuntimeError("SurveyManager must be used as async context manager.")
        return self._table

    def _calculate_ttl(self) -> int:
        """Calculate TTL timestamp 90 days from now."""
        return int((datetime.now() + timedelta(days=_SURVEY_TTL_DAYS)).timestamp())

    async def create_status(self, survey_id: str, user_id: str, channel_id: str) -> None:
        """Create survey status record for a user.

        Args:
            survey_id: Survey identifier (e.g., "survey_2026_q1")
            user_id: Slack user ID
            channel_id: DM channel ID for sending reminders
        """
        table = await self._get_table()

        try:
            await table.put_item(
                Item={
                    "thread_id": f"SURVEY_STATUS#{survey_id}#{user_id}",
                    "entity_type": "SURVEY_STATUS",
                    "survey_id": survey_id,
                    "user_id": user_id,
                    "completed": False,
                    "reminders_sent": 0,
                    "last_reminder_at": None,
                    "survey_channel_id": channel_id,
                    "created_at": datetime.now().isoformat(),
                    "ttl": self._calculate_ttl(),
                },
                ConditionExpression="attribute_not_exists(thread_id)",
            )
            logger.info("survey_status_created", survey_id=survey_id, user=user_id)
        except Exception as e:
            if "ConditionalCheckFailedException" in str(e):
                logger.info("survey_status_exists", survey_id=survey_id, user=user_id)
            else:
                raise

    async def has_status(self, survey_id: str, user_id: str) -> bool:
        """Check if a SURVEY_STATUS record exists for this user+survey."""
        table = await self._get_table()
        response = await table.get_item(
            Key={"thread_id": f"SURVEY_STATUS#{survey_id}#{user_id}"},
            ProjectionExpression="thread_id",
        )
        return "Item" in response

    async def mark_completed(self, survey_id: str, user_id: str) -> None:
        """Mark survey as completed for a user. Safe to call multiple times."""
        table = await self._get_table()

        await table.update_item(
            Key={"thread_id": f"SURVEY_STATUS#{survey_id}#{user_id}"},
            UpdateExpression="SET completed = :c, completed_at = :t",
            ExpressionAttributeValues={
                ":c": True,
                ":t": datetime.now().isoformat(),
            },
        )
        logger.info("survey_marked_completed", survey_id=survey_id, user=user_id)

    # Fields that must NEVER appear in anonymous response records
    _FORBIDDEN_RESPONSE_KEYS = frozenset(
        {
            "user_id",
            "user",
            "email",
            "name",
            "channel_id",
            "thread_id",
            "entity_type",
            "survey_id",
            "submitted_at",
            "ttl",
        }
    )

    async def store_response(self, survey_id: str, answers: dict[str, str]) -> None:
        """Store anonymous survey response (NO user_id).

        Defensively strips any PII or reserved keys from answers before storage.

        Args:
            survey_id: Survey identifier
            answers: Dict of question keys to answer values
        """
        table = await self._get_table()
        response_id = str(uuid.uuid4())

        # Strip forbidden keys to prevent PII injection or reserved field overwrites
        safe_answers = {k: v for k, v in answers.items() if k not in self._FORBIDDEN_RESPONSE_KEYS}

        item: dict[str, Any] = {
            "thread_id": f"SURVEY_RESPONSE#{survey_id}#{response_id}",
            "entity_type": "SURVEY_RESPONSE",
            "survey_id": survey_id,
            "submitted_at": datetime.now().isoformat(),
            "ttl": self._calculate_ttl(),
        }
        item.update(safe_answers)

        await table.put_item(Item=item)
        logger.info("survey_response_stored", survey_id=survey_id)

    async def get_pending_users(self, survey_id: str) -> list[dict]:
        """Get users who haven't completed the survey and have < 3 reminders.

        Returns list of dicts with user_id, reminders_sent, last_reminder_at,
        survey_channel_id.
        """
        table = await self._get_table()

        response = await table.query(
            IndexName="survey-by-type",
            KeyConditionExpression="entity_type = :et AND survey_id = :sid",
            FilterExpression="completed = :f AND reminders_sent < :max_r",
            ExpressionAttributeValues={
                ":et": "SURVEY_STATUS",
                ":sid": survey_id,
                ":f": False,
                ":max_r": 3,
            },
        )

        return response.get("Items", [])

    async def increment_reminder(self, survey_id: str, user_id: str) -> bool:
        """Atomically increment reminder count if 24h cooldown has passed.

        Uses DynamoDB ConditionExpression for idempotency. Catches
        ConditionalCheckFailedException from botocore ClientError.

        Returns:
            True if reminder was sent (condition passed), False otherwise.
        """
        table = await self._get_table()
        now = datetime.now()
        cutoff = (now - timedelta(hours=24)).isoformat()

        try:
            await table.update_item(
                Key={"thread_id": f"SURVEY_STATUS#{survey_id}#{user_id}"},
                UpdateExpression=(
                    "SET reminders_sent = if_not_exists(reminders_sent, :zero) + :one, "
                    "last_reminder_at = :now"
                ),
                ConditionExpression=(
                    "(attribute_not_exists(last_reminder_at) OR last_reminder_at = :null "
                    "OR last_reminder_at < :cutoff) "
                    "AND (attribute_not_exists(reminders_sent) OR reminders_sent < :max_r) "
                    "AND completed = :f"
                ),
                ExpressionAttributeValues={
                    ":zero": 0,
                    ":one": 1,
                    ":now": now.isoformat(),
                    ":null": None,
                    ":cutoff": cutoff,
                    ":max_r": 3,
                    ":f": False,
                },
            )
            logger.info("survey_reminder_incremented", survey_id=survey_id, user=user_id)
            return True
        except Exception as e:
            # botocore ClientError includes error code in str representation
            if "ConditionalCheckFailedException" in str(e):
                logger.info("survey_reminder_cooldown", survey_id=survey_id, user=user_id)
                return False
            raise

    async def get_results(self, survey_id: str) -> dict[str, Any]:
        """Get aggregated survey results for admin reporting.

        Returns:
            Dict with total_responses, total_sent, completion_rate, and
            per-question answer counts.
        """
        table = await self._get_table()

        # Get responses
        response = await table.query(
            IndexName="survey-by-type",
            KeyConditionExpression="entity_type = :et AND survey_id = :sid",
            ExpressionAttributeValues={
                ":et": "SURVEY_RESPONSE",
                ":sid": survey_id,
            },
        )
        responses = response.get("Items", [])

        # Get statuses for completion rate
        status_response = await table.query(
            IndexName="survey-by-type",
            KeyConditionExpression="entity_type = :et AND survey_id = :sid",
            ExpressionAttributeValues={
                ":et": "SURVEY_STATUS",
                ":sid": survey_id,
            },
        )
        statuses = status_response.get("Items", [])
        total_sent = len(statuses)
        total_completed = sum(1 for s in statuses if s.get("completed"))

        # Aggregate answers per question
        question_keys = ["question_1", "question_2", "question_3", "question_4"]
        aggregated: dict[str, dict[str, int]] = {q: {} for q in question_keys}
        for resp in responses:
            for q in question_keys:
                answer = resp.get(q, "")
                if answer:
                    aggregated[q][answer] = aggregated[q].get(answer, 0) + 1

        return {
            "survey_id": survey_id,
            "total_sent": total_sent,
            "total_responses": len(responses),
            "total_completed": total_completed,
            "completion_rate": round(total_completed / total_sent * 100, 1) if total_sent else 0,
            "answers": aggregated,
        }

    async def get_active_survey_ids(self) -> list[str]:
        """Get distinct survey IDs that have pending (uncompleted) statuses."""
        table = await self._get_table()

        response = await table.query(
            IndexName="survey-by-type",
            KeyConditionExpression="entity_type = :et",
            FilterExpression="completed = :f",
            ExpressionAttributeValues={
                ":et": "SURVEY_STATUS",
                ":f": False,
            },
            ProjectionExpression="survey_id",
        )

        items = response.get("Items", [])
        return list({item["survey_id"] for item in items})

    async def get_all_survey_ids(self) -> list[str]:
        """Get distinct survey IDs from all status records (for admin results)."""
        table = await self._get_table()

        response = await table.query(
            IndexName="survey-by-type",
            KeyConditionExpression="entity_type = :et",
            ExpressionAttributeValues={
                ":et": "SURVEY_STATUS",
            },
            ProjectionExpression="survey_id",
        )

        items = response.get("Items", [])
        return list({item["survey_id"] for item in items})
