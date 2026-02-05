"""Usage tracking with privacy-first design.

Records DM events (timestamp only) and provides admin-only retrieval.
"""

from datetime import datetime
from typing import Any

import structlog

logger = structlog.get_logger()


class UsageTracker:
    """Tracks usage events with timestamp-only privacy design.

    Records DM events to DynamoDB GSI for admin reporting.
    No user IDs are stored - only event timestamps.

    Must be used as async context manager:
        async with UsageTracker() as tracker:
            await tracker.record_event()
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

    async def __aenter__(self) -> "UsageTracker":
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
            raise RuntimeError("UsageTracker must be used as async context manager.")
        return self._table

    @staticmethod
    def is_admin(user_id: str, admin_ids: list[str]) -> bool:
        """Check if user is an admin who can retrieve usage data."""
        return user_id in admin_ids

    async def record_event(self) -> None:
        """Record a usage event (timestamp only - no user ID for privacy)."""
        table = await self._get_table()
        timestamp = datetime.utcnow().isoformat() + "Z"

        await table.put_item(
            Item={
                "thread_id": f"USAGE#{timestamp}",
                "entity_type": "USAGE",
                "timestamp": timestamp,
            }
        )
        logger.info("usage_event_recorded")

    async def get_usage(self, start: datetime, end: datetime) -> int:
        """Get usage count between start and end times (admin only).

        Args:
            start: Start of time range (inclusive)
            end: End of time range (inclusive)

        Returns:
            Count of usage events in the time range
        """
        table = await self._get_table()

        start_ts = start.isoformat() + "Z"
        end_ts = end.isoformat() + "Z"

        response = await table.query(
            IndexName="usage-by-timestamp",
            KeyConditionExpression="entity_type = :et AND #ts BETWEEN :start AND :end",
            ExpressionAttributeNames={"#ts": "timestamp"},
            ExpressionAttributeValues={
                ":et": "USAGE",
                ":start": start_ts,
                ":end": end_ts,
            },
            Select="COUNT",
        )

        count: int = response.get("Count", 0)
        logger.info("usage_retrieved", count=count, start=start_ts, end=end_ts)
        return count
